from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import floor
from random import uniform

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.broker import AlpacaBrokerAdapter, PaperBrokerAdapter
from app.adapters.market_data import AlpacaPolygonMarketDataAdapter, SetupMarketData
from app.core.config import Settings
from app.models.entities import AccountSettingsEntity, OrderEntity, PositionEntity, TradeLogEntity
from app.schemas.cockpit import (
    AccountSettingsUpdate,
    AccountSettingsView,
    LogEntry,
    OrderView,
    PositionView,
    ProfitRequest,
    SetupResponse,
    StopMode,
    StopsRequest,
    TradeEnterRequest,
    TradePreviewRequest,
    Tranche,
    TrancheMode,
)
from app.ws.manager import WebSocketManager


def utcnow() -> datetime:
    return datetime.now(UTC)


class CockpitService:
    def __init__(self, settings: Settings, ws_manager: WebSocketManager) -> None:
        self.settings = settings
        self.ws_manager = ws_manager
        self.market_data = AlpacaPolygonMarketDataAdapter(settings)
        self.broker = (
            AlpacaBrokerAdapter(settings)
            if settings.broker_mode in {"alpaca_paper", "alpaca_live"}
            else PaperBrokerAdapter()
        )

    def ensure_seed_data(self, db: Session) -> None:
        account = db.scalar(select(AccountSettingsEntity))
        if account is None:
            db.add(
                AccountSettingsEntity(
                    equity=self.settings.default_account_equity,
                    buying_power=self.settings.default_account_equity * 4,
                    risk_pct=self.settings.default_risk_pct,
                    mode=self.settings.broker_mode,
                    daily_realized_pnl=0.0,
                    updated_at=utcnow(),
                )
            )
            db.commit()
        if not db.scalars(select(TradeLogEntity)).first():
            self._log(db, None, "sys", "Cockpit initialized. Enter ticker to begin.")
            db.commit()

    def get_account(self, db: Session) -> AccountSettingsView:
        self.ensure_seed_data(db)
        account = db.scalar(select(AccountSettingsEntity))
        assert account is not None
        return AccountSettingsView(
            equity=account.equity,
            buying_power=account.buying_power,
            risk_pct=account.risk_pct,
            mode=account.mode,
            daily_realized_pnl=account.daily_realized_pnl,
        )

    def update_account(self, db: Session, payload: AccountSettingsUpdate) -> AccountSettingsView:
        self.ensure_seed_data(db)
        account = db.scalar(select(AccountSettingsEntity))
        assert account is not None
        account.equity = payload.equity
        account.buying_power = payload.equity * 4
        account.risk_pct = payload.risk_pct
        account.mode = payload.mode
        account.updated_at = utcnow()
        db.commit()
        self._log(db, None, "sys", f"Account settings updated: equity {payload.equity:.2f}")
        db.commit()
        return self.get_account(db)

    def get_setup(self, db: Session, symbol: str) -> SetupResponse:
        account = self.get_account(db)
        market = self.market_data.get_setup_data(symbol)
        return self._build_setup_response(market, account.equity, account.risk_pct)

    def preview_trade(self, db: Session, payload: TradePreviewRequest) -> dict:
        setup = self.get_setup(db, payload.symbol)
        per_share_risk = round(payload.entry - payload.stopPrice, 2)
        shares = self._calculate_shares(setup.accountEquity, payload.riskPct, per_share_risk)
        self._log(
            db,
            payload.symbol.upper(),
            "info",
            f"Preview: {payload.symbol.upper()} buy {shares} sh @ {payload.entry:.2f} stop {payload.stopPrice:.2f}",
        )
        db.commit()
        return {
            "symbol": payload.symbol.upper(),
            "entry": payload.entry,
            "finalStop": payload.stopPrice,
            "perShareRisk": per_share_risk,
            "shares": shares,
            "dollarRisk": round(setup.accountEquity * (payload.riskPct / 100), 2),
        }

    async def enter_trade(self, db: Session, payload: TradeEnterRequest) -> PositionView:
        symbol = payload.symbol.upper()
        setup = self.get_setup(db, symbol)
        self._enforce_risk_checks(db, symbol, payload.entry, setup.shares)
        qtys = self._split_shares(setup.shares, payload.trancheCount)
        tranches = [
            Tranche(
                id=f"T{i+1}",
                qty=qty,
                stop=payload.stopPrice,
                label=f"Tranche {i+1} · P{i+1}",
                mode=payload.trancheModes[i].mode,
                trail=payload.trancheModes[i].trail,
                trailUnit=payload.trancheModes[i].trailUnit,
            ).model_dump()
            for i, qty in enumerate(qtys)
        ]
        root_order_id = self._next_order_id(db)
        broker = self.broker.place_market_order(symbol, setup.shares, "buy")
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol))
        if position is None:
            position = PositionEntity(
                symbol=symbol,
                phase="trade_entered",
                entry_price=payload.entry,
                live_price=setup.last,
                shares=setup.shares,
                stop_ref=payload.stopRef,
                stop_price=payload.stopPrice,
                tranche_count=payload.trancheCount,
                tranche_modes=[item.model_dump() for item in payload.trancheModes],
                stop_modes=[StopMode().model_dump() for _ in range(3)],
                tranches=tranches,
                setup_snapshot=setup.model_dump(),
                root_order_id=root_order_id,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(position)
        else:
            position.phase = "trade_entered"
            position.entry_price = payload.entry
            position.live_price = setup.last
            position.shares = setup.shares
            position.stop_ref = payload.stopRef
            position.stop_price = payload.stopPrice
            position.tranche_count = payload.trancheCount
            position.tranche_modes = [item.model_dump() for item in payload.trancheModes]
            position.stop_modes = [StopMode().model_dump() for _ in range(3)]
            position.tranches = tranches
            position.setup_snapshot = setup.model_dump()
            position.root_order_id = root_order_id
            position.updated_at = utcnow()
            position.closed_at = None
        db.add(
            OrderEntity(
                order_id=root_order_id,
                broker_order_id=broker.broker_order_id,
                symbol=symbol,
                type="MKT",
                qty=setup.shares,
                orig_qty=setup.shares,
                price=payload.entry,
                status="FILLED",
                tranche_label=symbol,
                covered_tranches=[],
                parent_id=None,
                created_at=utcnow(),
                filled_at=utcnow(),
                fill_price=payload.entry,
            )
        )
        self._log(db, symbol, "exec", f"Trade entered: Buy {setup.shares} sh {symbol} @ {payload.entry:.2f}")
        db.commit()
        view = self.get_position(db, symbol)
        await self.ws_manager.broadcast("cockpit", {"type": "position_update", "symbol": symbol, "phase": view.phase, "pnl": 0.0})
        return view

    async def apply_stops(self, db: Session, payload: StopsRequest) -> PositionView:
        position = self._require_position(db, payload.symbol)
        self._reject_duplicate_active_stops(db, position.symbol)
        stop_range = round(position.entry_price - position.stop_price, 2)
        current_tranches = deepcopy(position.tranches)
        for index, group in enumerate(self._stop_groups(current_tranches, payload.stopMode)):
            config = payload.stopModes[index]
            pct = 100.0 if config.pct is None else config.pct
            price = (
                position.entry_price
                if config.mode == "be"
                else round(position.entry_price - stop_range * pct / 100.0, 2)
            )
            self._validate_stop(position.entry_price, price)
            qty = sum(item["qty"] for item in group)
            covered = [item["id"] for item in group]
            broker = self.broker.place_stop_order(position.symbol, qty, price)
            db.add(
                OrderEntity(
                    order_id=self._next_order_id(db),
                    broker_order_id=broker.broker_order_id,
                    symbol=position.symbol,
                    type="STOP",
                    qty=qty,
                    orig_qty=qty,
                    price=price,
                    status="ACTIVE",
                    tranche_label=f"S{index+1}",
                    covered_tranches=covered,
                    parent_id=position.root_order_id,
                    created_at=utcnow(),
                )
            )
            for tranche in current_tranches:
                if tranche["id"] in covered and tranche["status"] == "active":
                    tranche["stop"] = price
        position.tranches = current_tranches
        position.stop_modes = [item.model_dump() for item in payload.stopModes]
        position.phase = "protected"
        position.updated_at = utcnow()
        self._log(db, position.symbol, "warn", f"Stops applied in S{payload.stopMode} mode")
        db.commit()
        view = self.get_position(db, position.symbol)
        await self.ws_manager.broadcast("cockpit", {"type": "position_update", "symbol": position.symbol, "phase": view.phase, "pnl": self._pnl(view)})
        return view

    async def execute_profit_plan(self, db: Session, payload: ProfitRequest) -> PositionView:
        position = self._require_position(db, payload.symbol)
        tranches = deepcopy(position.tranches)
        per_share_risk = round(position.entry_price - position.stop_price, 2)
        phase = position.phase
        for index, tranche in enumerate(tranches):
            if tranche["status"] != "active":
                continue
            mode = payload.trancheModes[index]
            if mode.mode == "runner":
                runner_stop = self._trail_stop(position.live_price, mode.trail, mode.trailUnit)
                tranche["mode"] = "runner"
                tranche["runnerStop"] = runner_stop
                broker = self.broker.place_trailing_stop(position.symbol, tranche["qty"], mode.trail, mode.trailUnit)
                db.add(
                    OrderEntity(
                        order_id=self._next_order_id(db),
                        broker_order_id=broker.broker_order_id,
                        symbol=position.symbol,
                        type="TRAIL",
                        qty=tranche["qty"],
                        orig_qty=tranche["qty"],
                        price=runner_stop,
                        status="ACTIVE",
                        tranche_label=tranche["id"],
                        covered_tranches=[tranche["id"]],
                        parent_id=position.root_order_id,
                        created_at=utcnow(),
                    )
                )
                phase = "runner_only"
            else:
                target = self._resolve_target_price(position.entry_price, per_share_risk, mode)
                broker = self.broker.place_limit_order(position.symbol, tranche["qty"], target)
                db.add(
                    OrderEntity(
                        order_id=self._next_order_id(db),
                        broker_order_id=broker.broker_order_id,
                        symbol=position.symbol,
                        type="LMT",
                        qty=tranche["qty"],
                        orig_qty=tranche["qty"],
                        price=target,
                        status="FILLED",
                        tranche_label=tranche["id"],
                        covered_tranches=[],
                        parent_id=position.root_order_id,
                        created_at=utcnow(),
                        filled_at=utcnow(),
                        fill_price=target,
                    )
                )
                tranche["status"] = "sold"
                tranche["target"] = target
                self._reduce_stop_orders(db, position.symbol, tranche["id"], tranche["qty"])
                phase = "P1_done" if index == 0 else "P2_done"
        if all(tranche["status"] != "active" for tranche in tranches):
            phase = "closed"
            position.closed_at = utcnow()
        position.tranches = tranches
        position.tranche_modes = [item.model_dump() for item in payload.trancheModes]
        position.phase = phase
        position.updated_at = utcnow()
        executed = len([tranche for tranche in tranches if tranche["status"] == "sold"])
        self._log(db, position.symbol, "exec", f"\u2713 Profit plan executed \u2014 {executed} tranche(s) filled")
        db.commit()
        view = self.get_position(db, position.symbol)
        await self.ws_manager.broadcast("cockpit", {"type": "position_update", "symbol": position.symbol, "phase": view.phase, "pnl": self._pnl(view)})
        return view

    async def move_to_be(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        position.tranches = [
            {**tranche, "stop": position.entry_price} if tranche["status"] == "active" else tranche
            for tranche in deepcopy(position.tranches)
        ]
        for order in db.scalars(select(OrderEntity).where(OrderEntity.symbol == position.symbol, OrderEntity.type == "STOP")):
            if order.status in {"ACTIVE", "MODIFIED"}:
                order.price = position.entry_price
                order.status = "MODIFIED"
        position.phase = "protected"
        position.updated_at = utcnow()
        self._log(db, position.symbol, "warn", f"All stops \u2192 breakeven: {position.entry_price:.2f}")
        db.commit()
        return self.get_position(db, position.symbol)

    async def flatten(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        updated_tranches = []
        for order in db.scalars(select(OrderEntity).where(OrderEntity.symbol == position.symbol)):
            if order.type == "STOP" and order.status in {"ACTIVE", "MODIFIED"}:
                order.status = "CANCELED"
        for tranche in deepcopy(position.tranches):
            if tranche["status"] == "active":
                db.add(
                    OrderEntity(
                        order_id=self._next_order_id(db),
                        broker_order_id=None,
                        symbol=position.symbol,
                        type="MKT",
                        qty=tranche["qty"],
                        orig_qty=tranche["qty"],
                        price=position.live_price,
                        status="FILLED",
                        tranche_label=tranche["id"],
                        covered_tranches=[],
                        parent_id=position.root_order_id,
                        created_at=utcnow(),
                        filled_at=utcnow(),
                        fill_price=position.live_price,
                    )
                )
                tranche["status"] = "sold"
                tranche["target"] = position.live_price
            updated_tranches.append(tranche)
        position.tranches = updated_tranches
        position.phase = "closed"
        position.closed_at = utcnow()
        position.updated_at = utcnow()
        self._log(db, position.symbol, "close", "\u2B1B POSITION FLATTENED \u2014 all tranches closed @ market")
        db.commit()
        view = self.get_position(db, position.symbol)
        await self.ws_manager.broadcast("cockpit", {"type": "position_update", "symbol": position.symbol, "phase": view.phase, "pnl": self._pnl(view)})
        return view

    def get_positions(self, db: Session) -> list[PositionView]:
        positions = db.scalars(select(PositionEntity).order_by(PositionEntity.created_at.desc())).all()
        return [self._position_view(db, position) for position in positions]

    def get_position(self, db: Session, symbol: str) -> PositionView:
        return self._position_view(db, self._require_position(db, symbol))

    def get_orders(self, db: Session, symbol: str) -> list[OrderView]:
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol.upper()))
        if position is not None and position.root_order_id:
            rows = db.scalars(
                select(OrderEntity)
                .where(
                    OrderEntity.symbol == symbol.upper(),
                    (OrderEntity.order_id == position.root_order_id) | (OrderEntity.parent_id == position.root_order_id),
                )
                .order_by(OrderEntity.created_at.asc())
            ).all()
        else:
            rows = db.scalars(
                select(OrderEntity).where(OrderEntity.symbol == symbol.upper()).order_by(OrderEntity.created_at.asc())
            ).all()
        return [self._order_view(row) for row in rows]

    def get_logs(self, db: Session) -> list[LogEntry]:
        self.ensure_seed_data(db)
        rows = db.scalars(select(TradeLogEntity).order_by(TradeLogEntity.created_at.desc()).limit(200)).all()
        return [LogEntry.model_validate(row, from_attributes=True) for row in rows]

    def clear_logs(self, db: Session) -> int:
        rows = db.scalars(select(TradeLogEntity)).all()
        cleared = len(rows)
        for row in rows:
            db.delete(row)
        db.commit()
        self._log(db, None, "sys", "Log cleared.")
        db.commit()
        return cleared

    async def publish_price_tick(self, db: Session, symbol: str) -> None:
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol.upper()))
        if position is None:
            return
        position.live_price = round(max(0.01, position.live_price + uniform(-0.35, 0.35)), 2)
        position.updated_at = utcnow()
        db.commit()
        base = position.entry_price
        await self.ws_manager.broadcast(
            "cockpit",
            {
                "type": "price",
                "symbol": position.symbol,
                "bid": round(position.live_price - 0.03, 2),
                "ask": round(position.live_price + 0.03, 2),
                "last": position.live_price,
                "delta": round(position.live_price - base, 2),
                "delta_pct": round(((position.live_price - base) / base) * 100, 2) if base else 0.0,
            },
        )

    def _build_setup_response(self, market: SetupMarketData, equity: float, risk_pct: float) -> SetupResponse:
        entry = round((market.bid + market.ask) / 2, 2)
        final_stop = market.lod
        per_share_risk = round(max(0.01, entry - final_stop), 2)
        shares = self._calculate_shares(equity, risk_pct, per_share_risk)
        return SetupResponse(
            symbol=market.symbol,
            bid=market.bid,
            ask=market.ask,
            last=market.last,
            lod=market.lod,
            hod=market.hod,
            prev_close=market.prev_close,
            atr14=market.atr14,
            sma10=market.sma10,
            sma50=market.sma50,
            sma200=market.sma200,
            sma200_prev=market.sma200_prev,
            rvol=market.rvol,
            days_to_cover=market.days_to_cover,
            entry=entry,
            finalStop=final_stop,
            r1=round(entry + per_share_risk, 2),
            r2=round(entry + per_share_risk * 2, 2),
            r3=round(entry + per_share_risk * 3, 2),
            shares=shares,
            dollarRisk=round(equity * (risk_pct / 100), 2),
            perShareRisk=per_share_risk,
            riskPct=risk_pct,
            accountEquity=equity,
            atrExtension=round((entry - market.sma50) / market.atr14, 2),
            extFrom10Ma=round(((entry - market.sma10) / market.sma10) * 100, 2),
        )

    def _calculate_shares(self, equity: float, risk_pct: float, per_share_risk: float) -> int:
        if per_share_risk <= 0:
            return 0
        return max(1, floor((equity * (risk_pct / 100)) / per_share_risk))

    def _split_shares(self, shares: int, count: int) -> list[int]:
        if count <= 1:
            return [shares]
        if count == 2:
            first = shares // 2
            return [first, shares - first]
        first = floor(shares * 0.33)
        second = floor(shares * 0.33)
        return [first, second, shares - first - second]

    def _stop_groups(self, tranches: list[dict], stop_mode: int) -> list[list[dict]]:
        active = [tranche for tranche in tranches if tranche["status"] == "active"]
        if stop_mode <= 1:
            return [active]
        if stop_mode == 2:
            midpoint = max(1, len(active) // 2)
            return [active[:midpoint], active[midpoint:]]
        return [[tranche] for tranche in active]

    def _resolve_target_price(self, entry: float, per_share_risk: float, mode: TrancheMode) -> float:
        if mode.target == "Manual" and mode.manualPrice is not None:
            return round(mode.manualPrice, 2)
        multiplier = {"1R": 1, "2R": 2, "3R": 3}[mode.target]
        return round(entry + per_share_risk * multiplier, 2)

    def _trail_stop(self, live_price: float, trail: float, trail_unit: str) -> float:
        return round(live_price - trail, 2) if trail_unit == "$" else round(live_price * (1 - trail / 100), 2)

    def _reduce_stop_orders(self, db: Session, symbol: str, tranche_id: str, qty_sold: int) -> None:
        for order in db.scalars(select(OrderEntity).where(OrderEntity.symbol == symbol, OrderEntity.type == "STOP")):
            if order.status == "CANCELED" or tranche_id not in order.covered_tranches:
                continue
            order.qty = max(0, order.qty - qty_sold)
            order.covered_tranches = [item for item in order.covered_tranches if item != tranche_id]
            order.status = "CANCELED" if order.qty == 0 else "MODIFIED"

    def _enforce_risk_checks(self, db: Session, symbol: str, entry: float, shares: int) -> None:
        account = self.get_account(db)
        if entry * shares > account.equity * (self.settings.max_position_notional_pct / 100):
            raise ValueError("Position exceeds max notional cap")
        if account.daily_realized_pnl < -(account.equity * (self.settings.daily_loss_limit_pct / 100)):
            raise ValueError("Daily loss limit reached")
        open_positions = [row for row in self.get_positions(db) if row.phase != "closed"]
        if len(open_positions) >= self.settings.max_open_positions:
            raise ValueError("Max open positions reached")
        active = db.scalars(select(OrderEntity).where(OrderEntity.symbol == symbol, OrderEntity.status.in_(["ACTIVE", "MODIFIED"]))).all()
        if active:
            raise ValueError("Duplicate active orders exist for this symbol")

    def _validate_stop(self, entry: float, stop_price: float) -> None:
        if stop_price >= entry:
            raise ValueError("Stop price must be below entry")
        if stop_price <= entry * 0.5:
            raise ValueError("Stop price too far below entry")

    def _reject_duplicate_active_stops(self, db: Session, symbol: str) -> None:
        active = db.scalars(select(OrderEntity).where(OrderEntity.symbol == symbol, OrderEntity.type == "STOP", OrderEntity.status.in_(["ACTIVE", "MODIFIED"]))).all()
        if active:
            raise ValueError("Active stop orders already exist for this symbol")

    def _require_position(self, db: Session, symbol: str) -> PositionEntity:
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol.upper()))
        if position is None:
            raise ValueError(f"No position for {symbol.upper()}")
        return position

    def _next_order_id(self, db: Session) -> str:
        persisted_max = db.scalar(select(func.max(OrderEntity.id))) or 0
        pending_max = 0
        for instance in db.new:
            if isinstance(instance, OrderEntity) and instance.order_id.startswith("ORD-"):
                try:
                    pending_max = max(pending_max, int(instance.order_id.split("-", 1)[1]))
                except ValueError:
                    continue
        next_seq = max(persisted_max, pending_max) + 1
        return f"ORD-{next_seq:04d}"

    def _order_view(self, row: OrderEntity) -> OrderView:
        return OrderView(
            id=row.order_id,
            type=row.type,
            qty=row.qty,
            origQty=row.orig_qty,
            price=row.price,
            status=row.status,
            tranche=row.tranche_label,
            coveredTranches=list(row.covered_tranches or []),
            parentId=row.parent_id,
            brokerOrderId=row.broker_order_id,
        )

    def _position_view(self, db: Session, row: PositionEntity) -> PositionView:
        orders = self.get_orders(db, row.symbol)
        active_stops = [order for order in orders if order.type == "STOP" and order.status in {"ACTIVE", "MODIFIED"}]
        return PositionView(
            symbol=row.symbol,
            phase=row.phase,
            livePrice=row.live_price,
            setup=row.setup_snapshot,
            tranches=[Tranche.model_validate(item) for item in row.tranches],
            orders=orders,
            trancheModes=[TrancheMode.model_validate(item) for item in row.tranche_modes],
            stopModes=[StopMode.model_validate(item) for item in row.stop_modes],
            rootOrderId=row.root_order_id,
            stopMode=len(active_stops),
            trancheCount=row.tranche_count,
        )

    def _log(self, db: Session, symbol: str | None, tag: str, message: str) -> None:
        db.add(TradeLogEntity(symbol=symbol, tag=tag, message=message, created_at=utcnow()))

    def _pnl(self, position: PositionView) -> float:
        entry = float(position.setup.get("entry", 0.0))
        active_shares = sum(tranche.qty for tranche in position.tranches if tranche.status == "active")
        return round((position.livePrice - entry) * active_shares, 2)
