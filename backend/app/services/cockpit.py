from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import floor
from random import uniform

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.adapters.broker import AlpacaBrokerAdapter, BrokerEntryOrder, PaperBrokerAdapter
from app.adapters.market_data import AlpacaPolygonMarketDataAdapter, SetupMarketData
from app.core.config import Settings
from app.models.entities import AccountSettingsEntity, OrderEntity, PositionEntity, TradeLogEntity
from app.schemas.cockpit import (
    AccountSettingsUpdate,
    AccountSettingsView,
    EntryOrderDraft,
    LogEntry,
    OrderView,
    PositionView,
    ProfitRequest,
    SetupResponse,
    StopLossDraft,
    StopMode,
    StopsRequest,
    TakeProfitDraft,
    TradeEnterRequest,
    TradePreviewRequest,
    TradePreviewResponse,
    Tranche,
    TrancheMode,
)
from app.services.entry_order_rules import evaluate_entry_order_rules
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
        effective_mode = self._effective_account_mode(account.mode)
        equity = account.equity
        buying_power = account.buying_power
        cash = None
        equity_source = "local_settings"
        if effective_mode == "alpaca_paper":
            broker_summary = self.broker.get_account_summary()
            if broker_summary:
                equity = broker_summary.get("equity", equity)
                buying_power = broker_summary.get("buying_power", buying_power)
                cash = broker_summary.get("cash")
                equity_source = "alpaca_account"
        return AccountSettingsView(
            equity=equity,
            buying_power=buying_power,
            cash=cash,
            risk_pct=account.risk_pct,
            mode=account.mode,
            effective_mode=effective_mode,
            equity_source=equity_source,
            daily_realized_pnl=account.daily_realized_pnl,
            allow_live_trading=self.settings.allow_live_trading,
            max_position_notional_pct=self.settings.max_position_notional_pct,
            daily_loss_limit_pct=self.settings.daily_loss_limit_pct,
            max_open_positions=self.settings.max_open_positions,
            live_disabled_reason=self._live_disabled_reason(account.mode),
        )

    def update_account(self, db: Session, payload: AccountSettingsUpdate) -> AccountSettingsView:
        self.ensure_seed_data(db)
        if payload.mode == "alpaca_live" and self._live_disabled_reason(payload.mode):
            raise ValueError(self._live_disabled_reason(payload.mode) or "Live trading is disabled")
        account = db.scalar(select(AccountSettingsEntity))
        assert account is not None
        previous = (account.equity, account.risk_pct, account.mode)
        account.equity = payload.equity
        account.buying_power = payload.equity * 4
        account.risk_pct = payload.risk_pct
        account.mode = payload.mode
        account.updated_at = utcnow()
        db.commit()
        if previous != (payload.equity, payload.risk_pct, payload.mode):
            self._log(db, None, "sys", f"Account settings updated: equity {payload.equity:.2f}")
            db.commit()
        return self.get_account(db)

    def get_setup(self, db: Session, symbol: str) -> SetupResponse:
        account = self.get_account(db)
        market = self.market_data.get_setup_data(symbol)
        return self._build_setup_response(
            market,
            account.equity,
            account.buying_power,
            account.risk_pct,
            account.equity_source,
            account.cash,
        )

    def preview_trade(self, db: Session, payload: TradePreviewRequest) -> TradePreviewResponse:
        setup = self.get_setup(db, payload.symbol)
        order = self._normalize_entry_order(payload.order, payload.entry, payload.stopPrice)
        self._validate_entry_order(order, setup.sessionState)
        preview_entry = self._preview_entry_price(payload.entry, order)
        self._validate_stop(preview_entry, payload.stopPrice, order.side)
        per_share_risk = self._risk_per_share(preview_entry, payload.stopPrice, order.side)
        shares = self._calculate_shares(
            setup.accountEquity,
            setup.accountBuyingPower,
            preview_entry,
            payload.riskPct,
            per_share_risk,
        )
        sizing_warning = self._sizing_warning(setup.accountBuyingPower, preview_entry, shares)
        self._log(
            db,
            payload.symbol.upper(),
            "info",
            f"Preview: {payload.symbol.upper()} {order.side.upper()} {shares} sh {order.orderType.upper()} {order.timeInForce.upper()} @ {preview_entry:.2f} stop {payload.stopPrice:.2f}",
        )
        db.commit()
        return TradePreviewResponse(
            symbol=payload.symbol.upper(),
            entry=preview_entry,
            finalStop=payload.stopPrice,
            perShareRisk=per_share_risk,
            shares=shares,
            dollarRisk=round(setup.accountEquity * (payload.riskPct / 100), 2),
            sizingWarning=sizing_warning,
            orderType=order.orderType,
            timeInForce=order.timeInForce,
            orderClass=order.orderClass,
        )

    async def enter_trade(self, db: Session, payload: TradeEnterRequest) -> PositionView:
        symbol = payload.symbol.upper()
        setup = self.get_setup(db, symbol)
        order = self._normalize_entry_order(payload.order, payload.entry, payload.stopPrice)
        self._validate_entry_order(order, setup.sessionState)
        preview_entry = self._preview_entry_price(payload.entry, order)
        self._validate_stop(preview_entry, payload.stopPrice, order.side)
        self._validate_tranche_modes(payload.trancheCount, payload.trancheModes)
        per_share_risk = self._risk_per_share(preview_entry, payload.stopPrice, order.side)
        shares = self._calculate_shares(
            setup.accountEquity,
            setup.accountBuyingPower,
            preview_entry,
            setup.riskPct,
            per_share_risk,
        )
        if shares <= 0:
            raise ValueError(
                "Calculated shares is zero for this setup. Increase risk or choose a tighter valid stop."
            )
        self._enforce_risk_checks(db, symbol, preview_entry, shares)
        qtys = self._split_shares(shares, payload.trancheCount, payload.trancheModes)
        session_state = setup.sessionState
        enforce_alpaca_offhours = setup.executionProvider == "alpaca_paper"
        entry_message: str
        broker_status = "PENDING"
        root_order_type = self._local_entry_order_type(order)
        order_for_broker = self._build_broker_entry_order(
            symbol,
            shares,
            order,
            payload.offHoursMode,
            session_state,
            enforce_alpaca_offhours,
            setup.last,
        )
        broker = self.broker.place_entry_order(order_for_broker)
        broker_status = broker.status or "PENDING"
        entry_filled = self._entry_should_start_filled(
            order_for_broker, broker_status, session_state, enforce_alpaca_offhours
        )
        if payload.offHoursMode == "queue_for_open":
            broker_status = "PENDING"
            entry_filled = False
        if entry_filled and order_for_broker.order_type == "market":
            try:
                self.broker.wait_for_position(symbol, min_qty=shares, timeout_seconds=5.0)
                broker_status = "FILLED"
            except ValueError:
                entry_filled = False
                broker_status = "PENDING"
        if payload.offHoursMode == "queue_for_open":
            entry_message = "Market closed. Order accepted and queued for the next regular session."
        elif order_for_broker.extended_hours:
            entry_message = "Extended-hours limit order submitted."
        else:
            entry_message = (
                f"Trade entered: {order_for_broker.side.upper()} {shares} sh {symbol} {order_for_broker.order_type.upper()} "
                f"{order_for_broker.time_in_force.upper()} @ {preview_entry:.2f}"
            )
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
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol))
        if position is None:
            position = PositionEntity(
                symbol=symbol,
                phase="trade_entered" if entry_filled else "entry_pending",
                entry_price=preview_entry,
                live_price=setup.last,
                shares=shares,
                stop_ref=payload.stopRef,
                stop_price=payload.stopPrice,
                tranche_count=payload.trancheCount,
                tranche_modes=[item.model_dump() for item in payload.trancheModes],
                stop_modes=[StopMode().model_dump() for _ in range(3)],
                tranches=tranches,
                setup_snapshot={
                    **setup.model_dump(mode="json"),
                    "entryOrder": order.model_dump(mode="json"),
                },
                root_order_id=root_order_id,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(position)
        else:
            position.phase = "trade_entered" if entry_filled else "entry_pending"
            position.entry_price = preview_entry
            position.live_price = setup.last
            position.shares = shares
            position.stop_ref = payload.stopRef
            position.stop_price = payload.stopPrice
            position.tranche_count = payload.trancheCount
            position.tranche_modes = [item.model_dump() for item in payload.trancheModes]
            position.stop_modes = [StopMode().model_dump() for _ in range(3)]
            position.tranches = tranches
            position.setup_snapshot = {
                **setup.model_dump(mode="json"),
                "entryOrder": order.model_dump(mode="json"),
            }
            position.root_order_id = root_order_id
            position.updated_at = utcnow()
            position.closed_at = None
        db.add(
            OrderEntity(
                order_id=root_order_id,
                broker_order_id=broker.broker_order_id,
                symbol=symbol,
                type=root_order_type,
                qty=shares,
                orig_qty=shares,
                price=preview_entry,
                status="FILLED" if entry_filled else broker_status,
                tranche_label=symbol,
                covered_tranches=[],
                parent_id=None,
                created_at=utcnow(),
                filled_at=utcnow() if entry_filled else None,
                fill_price=preview_entry if entry_filled else None,
            )
        )
        if entry_filled:
            self._log(db, symbol, "exec", entry_message)
        else:
            self._log(db, symbol, "warn", entry_message)
        self._log(
            db,
            symbol,
            "sys",
            "Tranches: " + " \u00b7 ".join(f"T{i+1}={qty}sh" for i, qty in enumerate(qtys)),
        )
        db.commit()
        view = self.get_position(db, symbol)
        await self._broadcast_position_bundle(db, view, pnl=0.0)
        return view

    async def apply_stops(self, db: Session, payload: StopsRequest) -> PositionView:
        position = self._require_position(db, payload.symbol)
        self._ensure_position_is_open(position)
        self._ensure_position_filled(
            position, "Protective orders are unavailable until the entry order is filled."
        )
        self._validate_stop_mode(payload.stopMode, payload.stopModes)
        self._reject_duplicate_active_stops(db, position.symbol)
        position_side = self._position_side(position)
        exit_side = self._exit_side(position_side)
        direction = 1 if position_side == "buy" else -1
        stop_range = abs(round(position.entry_price - position.stop_price, 2))
        current_tranches = deepcopy(position.tranches)
        for index, group in enumerate(self._stop_groups(current_tranches, payload.stopMode)):
            config = payload.stopModes[index]
            pct = self._default_stop_pct(config, index, payload.stopMode)
            price = (
                position.entry_price
                if config.mode == "be"
                else round(position.entry_price - direction * stop_range * pct / 100.0, 2)
            )
            self._validate_stop(position.entry_price, price, position_side)
            qty = sum(item["qty"] for item in group)
            covered = [item["id"] for item in group]
            broker = self.broker.place_stop_order(position.symbol, qty, price, side=exit_side)
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
        stop_lines: list[str] = []
        for index, group in enumerate(self._stop_groups(current_tranches, payload.stopMode)):
            config = payload.stopModes[index]
            pct = self._default_stop_pct(config, index, payload.stopMode)
            qty = sum(item["qty"] for item in group)
            price = position.entry_price if config.mode == "be" else group[0]["stop"]
            stop_lines.append(f"S{index+1} {qty}sh @ {price:.2f} ({pct:.2f}%)")
        self._log(
            db,
            position.symbol,
            "warn",
            f"\u2713 Stops applied \u2014 {' \u00b7 '.join(stop_lines)}",
        )
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    async def execute_profit_plan(self, db: Session, payload: ProfitRequest) -> PositionView:
        position = self._require_position(db, payload.symbol)
        self._ensure_profit_actionable(position)
        self._validate_tranche_modes(position.tranche_count, payload.trancheModes)
        tranches = deepcopy(position.tranches)
        position_side = self._position_side(position)
        exit_side = self._exit_side(position_side)
        per_share_risk = abs(round(position.entry_price - position.stop_price, 2))
        phase = position.phase
        executed_count = 0
        self._cancel_broker_exit_orders(db, position.symbol, {"STOP"})
        for index, tranche in enumerate(tranches):
            if tranche["status"] != "active":
                continue
            mode = payload.trancheModes[index]
            if mode.mode == "runner":
                self._reject_duplicate_active_order(db, position.symbol, tranche["id"], "TRAIL")
                runner_stop = self._trail_stop(
                    position.live_price, mode.trail, mode.trailUnit, position_side
                )
                tranche["mode"] = "runner"
                tranche["runnerStop"] = runner_stop
                broker = self.broker.place_trailing_stop(
                    position.symbol, tranche["qty"], mode.trail, mode.trailUnit, side=exit_side
                )
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
                self._reject_duplicate_active_order(db, position.symbol, tranche["id"], "LMT")
                target = self._resolve_target_price(
                    position.entry_price, per_share_risk, mode, position_side
                )
                broker = self.broker.place_limit_order(
                    position.symbol, tranche["qty"], target, side=exit_side
                )
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
                tranche["exitPrice"] = target
                tranche["exitFilledAt"] = utcnow().isoformat()
                tranche["exitOrderType"] = "LMT"
                self._reduce_stop_orders(db, position.symbol, tranche["id"], tranche["qty"])
                phase = "P1_done" if index == 0 else "P2_done"
                executed_count += 1
        if all(tranche["status"] != "active" for tranche in tranches):
            phase = "closed"
            position.closed_at = utcnow()
        position.tranches = tranches
        position.tranche_modes = [item.model_dump() for item in payload.trancheModes]
        position.phase = phase
        position.updated_at = utcnow()
        if executed_count == 0 and phase == "runner_only":
            raise ValueError("No executable profit tranches remain; runner already active")
        self._log(
            db,
            position.symbol,
            "exec",
            f"\u2713 Profit plan executed \u2014 {executed_count} tranche(s) filled",
        )
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    async def move_to_be(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        self._ensure_position_is_open(position)
        self._ensure_position_filled(
            position, "Protective orders are unavailable until the entry order is filled."
        )
        position.tranches = [
            {**tranche, "stop": position.entry_price} if tranche["status"] == "active" else tranche
            for tranche in deepcopy(position.tranches)
        ]
        for order in db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == position.symbol, OrderEntity.type == "STOP"
            )
        ):
            if order.status in {"ACTIVE", "MODIFIED"}:
                order.price = position.entry_price
                order.status = "MODIFIED"
        position.phase = "protected"
        position.updated_at = utcnow()
        self._log(
            db, position.symbol, "warn", f"All stops \u2192 breakeven: {position.entry_price:.2f}"
        )
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    async def flatten(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        self._ensure_position_is_open(position)
        if position.phase == "entry_pending":
            root_order = db.scalar(
                select(OrderEntity).where(OrderEntity.order_id == position.root_order_id)
            )
            if root_order and root_order.broker_order_id:
                self.broker.cancel_order(root_order.broker_order_id)
            if root_order:
                root_order.status = "CANCELED"
            canceled_tranches = []
            for tranche in deepcopy(position.tranches):
                tranche["status"] = "canceled"
                canceled_tranches.append(tranche)
            position.tranches = canceled_tranches
            for order in db.scalars(
                select(OrderEntity).where(OrderEntity.symbol == position.symbol)
            ):
                if order.status in {"ACTIVE", "MODIFIED", "PENDING"}:
                    if order.broker_order_id:
                        self.broker.cancel_order(order.broker_order_id)
                    order.status = "CANCELED"
            position.phase = "closed"
            position.closed_at = utcnow()
            position.updated_at = utcnow()
            self._log(db, position.symbol, "close", "Pending entry canceled before fill.")
            db.commit()
            view = self.get_position(db, position.symbol)
            await self._broadcast_position_bundle(db, view)
            return view
        updated_tranches = []
        broker_result = self.broker.close_position(position.symbol)
        for order in db.scalars(select(OrderEntity).where(OrderEntity.symbol == position.symbol)):
            if order.status in {"ACTIVE", "MODIFIED"}:
                if order.broker_order_id:
                    self.broker.cancel_order(order.broker_order_id)
                order.status = "CANCELED"
        for tranche in deepcopy(position.tranches):
            if tranche["status"] == "active":
                db.add(
                    OrderEntity(
                        order_id=self._next_order_id(db),
                        broker_order_id=broker_result.broker_order_id,
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
                tranche["exitPrice"] = position.live_price
                tranche["exitFilledAt"] = utcnow().isoformat()
                tranche["exitOrderType"] = "MKT"
            updated_tranches.append(tranche)
        position.tranches = updated_tranches
        position.phase = "closed"
        position.closed_at = utcnow()
        position.updated_at = utcnow()
        self._log(
            db,
            position.symbol,
            "close",
            "\u2b1b POSITION FLATTENED \u2014 all tranches closed @ market",
        )
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    def get_positions(self, db: Session) -> list[PositionView]:
        self._reconcile_all_positions(db)
        positions = db.scalars(
            select(PositionEntity).order_by(PositionEntity.created_at.desc())
        ).all()
        return [self._position_view(db, position) for position in positions]

    def get_position(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        if self._reconcile_position(db, position):
            db.commit()
        return self._position_view(db, position)

    def get_orders(self, db: Session, symbol: str) -> list[OrderView]:
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol.upper()))
        if position is not None:
            if self._reconcile_position(db, position):
                db.commit()
        if position is not None and position.root_order_id:
            rows = db.scalars(
                select(OrderEntity)
                .where(
                    OrderEntity.symbol == symbol.upper(),
                    (OrderEntity.order_id == position.root_order_id)
                    | (OrderEntity.parent_id == position.root_order_id),
                )
                .order_by(OrderEntity.created_at.asc())
            ).all()
        else:
            rows = db.scalars(
                select(OrderEntity)
                .where(OrderEntity.symbol == symbol.upper())
                .order_by(OrderEntity.created_at.asc())
            ).all()
        position_side = self._position_side(position)
        return [self._order_view(row, position_side=position_side) for row in rows]

    def get_recent_orders(self, db: Session, limit: int = 50) -> list[OrderView]:
        broker_orders_by_symbol = self._recent_broker_orders_by_symbol(limit=max(limit, 100))
        self._reconcile_all_positions(db, broker_orders_by_symbol)
        position_side_by_symbol = {
            position.symbol.upper(): self._position_side(position)
            for position in db.scalars(select(PositionEntity)).all()
        }
        try:
            broker_payloads = self.broker.list_recent_orders(limit=limit)
        except ValueError:
            broker_payloads = []
        broker_orders = {
            order["id"]: order
            for order in broker_payloads
            if isinstance(order, dict) and order.get("id")
        }
        rows = db.scalars(
            select(OrderEntity).order_by(OrderEntity.created_at.desc()).limit(limit * 3)
        ).all()
        merged: list[OrderView] = []
        seen_broker_ids: set[str] = set()
        for row in rows:
            broker_payload = broker_orders.get(row.broker_order_id or "")
            if broker_payload is not None:
                seen_broker_ids.add(str(broker_payload.get("id")))
            merged.append(
                self._order_view(
                    row,
                    broker_payload,
                    position_side=position_side_by_symbol.get(row.symbol.upper(), "buy"),
                )
            )
        for broker_order_id, broker_payload in broker_orders.items():
            if broker_order_id in seen_broker_ids:
                continue
            merged.append(self._broker_order_view(broker_payload))
        merged.sort(
            key=lambda item: (
                item.updatedAt
                or item.filledAt
                or item.createdAt
                or datetime.min.replace(tzinfo=UTC)
            ),
            reverse=True,
        )
        return merged[:limit]

    def cancel_recent_order(self, db: Session, broker_order_id: str) -> OrderView:
        broker_order = self.broker.get_order(broker_order_id)
        if broker_order is None:
            raise ValueError("Broker order was not found.")
        if not self._broker_order_cancelable(broker_order):
            raise ValueError("Broker order is no longer cancelable.")
        self.broker.cancel_order(broker_order_id)
        refreshed = self.broker.get_order(broker_order_id) or {**broker_order, "status": "canceled"}
        local_orders = db.scalars(
            select(OrderEntity).where(OrderEntity.broker_order_id == broker_order_id)
        ).all()
        for local in local_orders:
            local.status = str(refreshed.get("status", "canceled")).upper()
        self._reconcile_canceled_root_orders(db, local_orders)
        if local_orders:
            self._log(
                db,
                local_orders[0].symbol,
                "warn",
                f"Canceled broker order {broker_order_id} for {local_orders[0].symbol}.",
            )
        db.commit()
        local = local_orders[0] if local_orders else None
        local_position = (
            db.scalar(select(PositionEntity).where(PositionEntity.symbol == local.symbol))
            if local is not None
            else None
        )
        return (
            self._order_view(local, refreshed, position_side=self._position_side(local_position))
            if local is not None
            else self._broker_order_view(refreshed)
        )

    def get_logs(self, db: Session) -> list[LogEntry]:
        self.ensure_seed_data(db)
        rows = db.scalars(
            select(TradeLogEntity).order_by(TradeLogEntity.created_at.desc()).limit(200)
        ).all()
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
        self._reconcile_position(db, position)
        db.commit()
        base = position.entry_price
        await self.ws_manager.broadcast(
            "cockpit",
            self._event(
                "price_update",
                symbol=position.symbol,
                bid=round(position.live_price - 0.03, 2),
                ask=round(position.live_price + 0.03, 2),
                last=position.live_price,
                delta=round(position.live_price - base, 2),
                delta_pct=round(((position.live_price - base) / base) * 100, 2) if base else 0.0,
            ),
        )
        view = self._position_view(db, position)
        await self._broadcast_position_bundle(db, view)

    def _reconcile_all_positions(
        self,
        db: Session,
        broker_orders_by_symbol: dict[str, dict[str, dict]] | None = None,
    ) -> None:
        changed = False
        for position in db.scalars(select(PositionEntity)).all():
            symbol_orders = None
            if broker_orders_by_symbol is not None:
                symbol_orders = broker_orders_by_symbol.get(position.symbol.upper(), {})
            changed = self._reconcile_position(db, position, symbol_orders) or changed
        if changed:
            db.commit()

    def _reconcile_position(
        self,
        db: Session,
        position: PositionEntity,
        broker_orders: dict[str, dict] | None = None,
    ) -> bool:
        changed = False
        symbol_orders = (
            broker_orders
            if broker_orders is not None
            else self._broker_orders_for_symbol(position.symbol)
        )
        root_order = db.scalar(
            select(OrderEntity).where(OrderEntity.order_id == position.root_order_id)
        )
        if position.phase == "entry_pending" and root_order is not None:
            root_payload = symbol_orders.get(root_order.broker_order_id or "")
            if root_payload is not None and str(root_payload.get("status", "")).lower() == "filled":
                self._mark_entry_filled_if_ready(db, position)
                root_order.fill_price = (
                    self._broker_fill_price(root_payload, root_order.fill_price)
                    or position.entry_price
                )
                root_order.filled_at = (
                    self._broker_timestamp(root_payload, "filled_at")
                    or root_order.filled_at
                    or utcnow()
                )
                changed = True
        exit_orders = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == position.symbol,
                OrderEntity.type.in_(["STOP", "TRAIL"]),
                OrderEntity.status.in_(["ACTIVE", "MODIFIED", "NEW", "ACCEPTED"]),
            )
        ).all()
        for order in exit_orders:
            fill_details = self._resolve_exit_fill(
                position, order, symbol_orders.get(order.broker_order_id or "")
            )
            if fill_details is None:
                continue
            changed = self._apply_exit_fill(db, position, order, fill_details) or changed
        return changed

    def _recent_broker_orders_by_symbol(self, limit: int = 100) -> dict[str, dict[str, dict]]:
        try:
            recent = self.broker.list_recent_orders(limit=limit)
        except ValueError:
            return {}
        grouped: dict[str, dict[str, dict]] = {}
        for order in recent:
            if not isinstance(order, dict):
                continue
            symbol = str(order.get("symbol") or "").upper()
            broker_order_id = str(order.get("id") or "")
            if not symbol or not broker_order_id:
                continue
            grouped.setdefault(symbol, {})[broker_order_id] = order
        return grouped

    def _broker_orders_for_symbol(self, symbol: str) -> dict[str, dict]:
        return dict(self._recent_broker_orders_by_symbol(limit=100).get(symbol.upper(), {}))

    def _resolve_exit_fill(
        self,
        position: PositionEntity,
        order: OrderEntity,
        broker_payload: dict | None,
    ) -> dict[str, object] | None:
        if broker_payload is not None:
            status = str(broker_payload.get("status") or "").lower()
            if status == "canceled":
                order.status = "CANCELED"
                return None
            if status not in {"filled", "partially_filled"}:
                return None
            return {
                "status": status.upper(),
                "fill_price": self._broker_fill_price(broker_payload, order.fill_price)
                or order.price,
                "filled_at": self._broker_timestamp(broker_payload, "filled_at") or utcnow(),
                "filled_qty": max(0, self._broker_filled_qty(broker_payload) or order.orig_qty),
            }
        if order.status not in {"ACTIVE", "MODIFIED"}:
            return None
        if position.phase == "entry_pending":
            return None
        position_side = self._position_side(position)
        if position_side == "sell":
            if position.live_price < order.price:
                return None
        elif position.live_price > order.price:
            return None
        return {
            "status": "FILLED",
            "fill_price": order.price,
            "filled_at": utcnow(),
            "filled_qty": order.orig_qty,
        }

    def _apply_exit_fill(
        self,
        db: Session,
        position: PositionEntity,
        order: OrderEntity,
        fill_details: dict[str, object],
    ) -> bool:
        active_ids = {
            tranche["id"] for tranche in position.tranches if tranche["status"] == "active"
        }
        covered = [
            tranche_id
            for tranche_id in (
                order.covered_tranches
                or ([order.tranche_label] if order.tranche_label.startswith("T") else [])
            )
            if tranche_id in active_ids
        ]
        if not covered:
            order.status = str(fill_details["status"])
            order.fill_price = float(fill_details["fill_price"])
            order.filled_at = fill_details["filled_at"]  # type: ignore[assignment]
            return True
        tranches = deepcopy(position.tranches)
        filled_at = fill_details["filled_at"]
        fill_price = float(fill_details["fill_price"])
        for tranche in tranches:
            if tranche["id"] not in covered or tranche["status"] != "active":
                continue
            tranche["status"] = "sold"
            tranche["target"] = fill_price
            tranche["exitPrice"] = fill_price
            tranche["exitFilledAt"] = (
                filled_at.isoformat() if isinstance(filled_at, datetime) else str(filled_at)
            )
            tranche["exitOrderType"] = order.type
        order.status = str(fill_details["status"])
        order.fill_price = fill_price
        order.filled_at = filled_at if isinstance(filled_at, datetime) else utcnow()
        position.tranches = tranches
        position.phase = self._phase_from_tranches(position, tranches)
        position.updated_at = utcnow()
        if position.phase == "closed":
            position.closed_at = position.closed_at or utcnow()
        else:
            position.closed_at = None
        verb = "Stop hit" if order.type == "STOP" else "Runner stop filled"
        self._log(
            db,
            position.symbol,
            "warn" if order.type == "STOP" else "exec",
            f"{verb}: {' · '.join(covered)} @ {fill_price:.2f}",
        )
        db.flush()
        return True

    def _phase_from_tranches(self, position: PositionEntity, tranches: list[dict]) -> str:
        active = [tranche for tranche in tranches if tranche["status"] == "active"]
        if not active:
            return "closed"
        runner_active = any(tranche.get("mode") == "runner" for tranche in active)
        sold_count = sum(1 for tranche in tranches if tranche["status"] == "sold")
        if runner_active and len(active) == 1:
            return "runner_only"
        if sold_count >= 2:
            return "P2_done"
        if sold_count >= 1:
            return "P1_done"
        return "protected"

    def _position_side(self, position: PositionEntity | PositionView | dict | None) -> str:
        if position is None:
            return "buy"
        if isinstance(position, dict):
            setup_snapshot = position.get("setup") or position.get("setup_snapshot") or {}
        else:
            setup_snapshot = getattr(position, "setup_snapshot", None) or getattr(
                position, "setup", {}
            )
        if isinstance(setup_snapshot, dict):
            entry_order = setup_snapshot.get("entryOrder")
            if isinstance(entry_order, dict) and entry_order.get("side") == "sell":
                return "sell"
        return "buy"

    def _exit_side(self, side: str) -> str:
        return "buy" if side == "sell" else "sell"

    def _risk_per_share(self, entry: float, stop_price: float, side: str) -> float:
        return round((stop_price - entry) if side == "sell" else (entry - stop_price), 2)

    def _build_setup_response(
        self,
        market: SetupMarketData,
        equity: float,
        buying_power: float,
        risk_pct: float,
        equity_source: str,
        cash: float | None = None,
    ) -> SetupResponse:
        entry = round((market.bid + market.ask) / 2, 2)
        lod_stop = round(market.lod, 2)
        atr_stop = round(max(0.01, entry - market.atr14), 2)
        lod_is_valid = lod_stop < entry
        atr_is_valid = 0 < atr_stop < entry
        stop_reference_default = "lod" if lod_is_valid else "manual"
        final_stop = lod_stop if lod_is_valid else 0.0
        manual_stop_warning = (
            None
            if lod_is_valid
            else "Low of day is above the current entry price. Enter a manual stop for this setup."
        )
        per_share_risk = round(entry - final_stop, 2) if lod_is_valid else 0.0
        shares = self._calculate_shares(equity, buying_power, entry, risk_pct, per_share_risk)
        sizing_warning = self._sizing_warning(buying_power, entry, shares)
        buying_power_note = self._buying_power_note(equity, buying_power, cash, equity_source)
        return SetupResponse(
            symbol=market.symbol,
            provider=market.provider,
            providerState=market.provider_state,
            quoteProvider=market.quote_provider,
            technicalsProvider=market.technicals_provider,
            executionProvider=self.settings.broker_execution_provider,
            quoteIsReal=market.quote_is_real,
            technicalsAreFallback=market.technicals_are_fallback,
            fallbackReason=market.fallback_reason,
            quoteTimestamp=market.quote_timestamp,
            sessionState=market.session_state,
            quoteState=market.quote_state,
            entryBasis=market.entry_basis,
            stopReferenceDefault=stop_reference_default,
            lodIsValid=lod_is_valid,
            atrIsValid=atr_is_valid,
            lodStop=lod_stop,
            atrStop=atr_stop,
            manualStopWarning=manual_stop_warning,
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
            r1=round(entry + per_share_risk, 2) if per_share_risk > 0 else entry,
            r2=round(entry + per_share_risk * 2, 2) if per_share_risk > 0 else entry,
            r3=round(entry + per_share_risk * 3, 2) if per_share_risk > 0 else entry,
            shares=shares,
            dollarRisk=round(equity * (risk_pct / 100), 2),
            perShareRisk=per_share_risk,
            riskPct=risk_pct,
            accountEquity=equity,
            accountBuyingPower=buying_power,
            accountCash=cash,
            equitySource=equity_source,
            sizingWarning=sizing_warning,
            buyingPowerNote=buying_power_note,
            atrExtension=round((entry - market.sma50) / market.atr14, 2),
            extFrom10Ma=round(((entry - market.sma10) / market.sma10) * 100, 2),
        )

    def _calculate_shares(
        self,
        equity: float,
        buying_power: float,
        entry: float,
        risk_pct: float,
        per_share_risk: float,
    ) -> int:
        if per_share_risk <= 0 or entry <= 0:
            return 0
        risk_budget = floor((equity * (risk_pct / 100)) / per_share_risk)
        max_notional = equity * (self.settings.max_position_notional_pct / 100)
        effective_notional_cap = (
            min(buying_power, max_notional) if buying_power > 0 else max_notional
        )
        buying_power_cap = (
            floor(effective_notional_cap / entry) if effective_notional_cap > 0 else 0
        )
        capped = min(risk_budget, buying_power_cap)
        return max(0, capped)

    def _sizing_warning(self, buying_power: float, entry: float, shares: int) -> str | None:
        if entry > 0 and buying_power > 0 and buying_power < entry:
            return "Insufficient buying power to fund even one share at the current entry price."
        if buying_power <= 0:
            return "Broker buying power is unavailable or zero."
        if shares <= 0:
            return "Calculated shares is zero for this setup."
        return None

    def _buying_power_note(
        self,
        equity: float,
        buying_power: float,
        cash: float | None,
        equity_source: str,
    ) -> str | None:
        if equity_source != "alpaca_account":
            return None
        if buying_power <= 0:
            return "Live broker buying power is unavailable or fully reserved by current Alpaca paper orders or positions."
        if cash is not None and buying_power <= cash:
            return "Live broker buying power is currently limited by open or pending Alpaca paper orders and positions."
        if equity > 0 and buying_power < equity * 0.25:
            return "Live broker buying power is currently much lower than equity because Alpaca is reserving capital for open or pending paper orders."
        return None

    def _split_shares(
        self,
        shares: int,
        count: int,
        tranche_modes: list[TrancheMode] | None = None,
    ) -> list[int]:
        if count <= 1:
            return [shares]
        if shares <= 0:
            return [0 for _ in range(count)]
        if not tranche_modes:
            tranche_modes = []
        allocations = self._normalize_allocation_pcts(tranche_modes, count)
        raw_shares = [shares * (allocation / 100.0) for allocation in allocations]
        assigned = [floor(value) for value in raw_shares]
        remainder = shares - sum(assigned)
        remainders = sorted(
            ((raw_shares[index] - assigned[index], index) for index in range(count)),
            key=lambda item: (-item[0], item[1]),
        )
        for _, index in remainders[:remainder]:
            assigned[index] += 1
        return assigned

    def _normalize_allocation_pcts(
        self, tranche_modes: list[TrancheMode], count: int
    ) -> list[float]:
        active = tranche_modes[:count]
        if count == 1:
            return [100.0]
        default = 100.0 / count
        provided = [
            mode.allocationPct if mode.allocationPct is not None else default for mode in active
        ]
        total = sum(provided)
        if total <= 0:
            return [round(default, 2) for _ in range(count - 1)] + [
                round(100.0 - round(default, 2) * (count - 1), 2)
            ]
        normalized = [round((value / total) * 100.0, 2) for value in provided]
        normalized[-1] = round(100.0 - sum(normalized[:-1]), 2)
        return normalized

    def _stop_groups(self, tranches: list[dict], stop_mode: int) -> list[list[dict]]:
        active = [tranche for tranche in tranches if tranche["status"] == "active"]
        if stop_mode <= 1:
            return [active]
        if stop_mode == 2:
            midpoint = max(1, len(active) // 2)
            return [active[:midpoint], active[midpoint:]]
        return [[tranche] for tranche in active]

    def _default_stop_pct(self, config: StopMode, index: int, stop_mode: int) -> float:
        if config.mode == "be":
            return 0.0
        if config.pct is not None:
            return config.pct
        base = floor(100 / stop_mode)
        return float(100 - base * index) if index == stop_mode - 1 else float(base)

    def _resolve_target_price(
        self, entry: float, per_share_risk: float, mode: TrancheMode, side: str = "buy"
    ) -> float:
        if mode.target == "Manual" and mode.manualPrice is not None:
            return round(mode.manualPrice, 2)
        multiplier = {"1R": 1, "2R": 2, "3R": 3}[mode.target]
        direction = -1 if side == "sell" else 1
        return round(entry + direction * per_share_risk * multiplier, 2)

    def _trail_stop(
        self, live_price: float, trail: float, trail_unit: str, side: str = "buy"
    ) -> float:
        direction = -1 if side == "sell" else 1
        return (
            round(live_price - direction * trail, 2)
            if trail_unit == "$"
            else round(live_price * (1 - direction * trail / 100), 2)
        )

    def _reduce_stop_orders(self, db: Session, symbol: str, tranche_id: str, qty_sold: int) -> None:
        for order in db.scalars(
            select(OrderEntity).where(OrderEntity.symbol == symbol, OrderEntity.type == "STOP")
        ):
            if order.status == "CANCELED" or tranche_id not in order.covered_tranches:
                continue
            order.qty = max(0, order.qty - qty_sold)
            order.covered_tranches = [item for item in order.covered_tranches if item != tranche_id]
            order.status = "CANCELED" if order.qty == 0 else "MODIFIED"

    def _enforce_risk_checks(self, db: Session, symbol: str, entry: float, shares: int) -> None:
        account = self.get_account(db)
        if entry * shares > account.equity * (self.settings.max_position_notional_pct / 100):
            raise ValueError("Position exceeds max notional cap")
        if account.daily_realized_pnl < -(
            account.equity * (self.settings.daily_loss_limit_pct / 100)
        ):
            raise ValueError("Daily loss limit reached")
        open_positions = [row for row in self.get_positions(db) if row.phase != "closed"]
        if len(open_positions) >= self.settings.max_open_positions:
            raise ValueError("Max open positions reached")
        self._cancel_stale_active_orders(db, symbol)
        active = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == symbol, OrderEntity.status.in_(["ACTIVE", "MODIFIED"])
            )
        ).all()
        if active:
            raise ValueError("Duplicate active orders exist for this symbol")

    def _normalize_entry_order(
        self, order: EntryOrderDraft, entry: float, protective_stop: float
    ) -> EntryOrderDraft:
        normalized = order.model_copy(deep=True)
        direction = -1 if normalized.side == "sell" else 1
        protective_risk = max(abs(entry - protective_stop), 0.01)
        if normalized.orderType in {"limit", "stop_limit"} and normalized.limitPrice is None:
            normalized.limitPrice = round(entry, 2)
        if normalized.orderType == "stop" and normalized.stopPrice is None:
            normalized.stopPrice = round(entry, 2)
        if normalized.orderType == "stop_limit" and normalized.stopPrice is None:
            normalized.stopPrice = round(entry, 2)
        if normalized.orderClass in {"bracket", "oco"}:
            normalized.takeProfit = normalized.takeProfit or TakeProfitDraft(
                limitPrice=round(entry + direction * protective_risk, 2)
            )
            normalized.stopLoss = normalized.stopLoss or StopLossDraft(
                stopPrice=protective_stop, limitPrice=None
            )
        if normalized.orderClass == "oto":
            if normalized.otoExitSide == "take_profit":
                normalized.takeProfit = normalized.takeProfit or TakeProfitDraft(
                    limitPrice=round(entry + direction * protective_risk, 2)
                )
                normalized.stopLoss = None
            else:
                normalized.stopLoss = normalized.stopLoss or StopLossDraft(
                    stopPrice=protective_stop, limitPrice=None
                )
                normalized.takeProfit = None
        return normalized

    def _preview_entry_price(self, entry: float, order: EntryOrderDraft) -> float:
        if order.orderType == "stop" and order.stopPrice is not None:
            return round(order.stopPrice, 2)
        if order.orderType == "stop_limit" and order.limitPrice is not None:
            return round(order.limitPrice, 2)
        if order.limitPrice is not None and order.orderType == "limit":
            return round(order.limitPrice, 2)
        return round(entry, 2)

    def _validate_entry_order(self, order: EntryOrderDraft, session_state: str) -> None:
        rules = evaluate_entry_order_rules(order, session_state)
        if rules.errors:
            raise ValueError(" ".join(rules.errors))

    def _build_broker_entry_order(
        self,
        symbol: str,
        shares: int,
        order: EntryOrderDraft,
        off_hours_mode: str | None,
        session_state: str,
        enforce_alpaca_offhours: bool,
        reference_price: float,
    ) -> BrokerEntryOrder:
        extended_hours = False
        order_type = order.orderType
        tif = order.timeInForce
        limit_price = order.limitPrice
        if session_state != "regular_open" and enforce_alpaca_offhours:
            if off_hours_mode == "queue_for_open":
                order_type = "market"
                tif = "day"
            elif off_hours_mode == "extended_hours_limit":
                order_type = "limit"
                tif = "day"
                extended_hours = True
            elif order.orderType == "market":
                raise ValueError(
                    "Market is outside the regular session. Choose Queue For Open or Submit Extended-Hours Limit."
                )
        stop_loss = order.stopLoss
        take_profit = order.takeProfit
        return BrokerEntryOrder(
            symbol=symbol,
            qty=shares,
            side=order.side,
            order_type=order_type,
            time_in_force=tif,
            limit_price=limit_price,
            stop_price=order.stopPrice,
            order_class=order.orderClass,
            extended_hours=extended_hours or order.extendedHours,
            take_profit_limit_price=take_profit.limitPrice if take_profit else None,
            stop_loss_stop_price=stop_loss.stopPrice if stop_loss else None,
            stop_loss_limit_price=stop_loss.limitPrice if stop_loss else None,
            reference_price=reference_price,
        )

    def _entry_should_start_filled(
        self,
        order: BrokerEntryOrder,
        broker_status: str,
        session_state: str,
        enforce_alpaca_offhours: bool,
    ) -> bool:
        if broker_status.upper() == "FILLED":
            return True
        if enforce_alpaca_offhours and session_state != "regular_open":
            return False
        return order.order_class == "simple" and order.order_type == "market"

    def _local_entry_order_type(self, order: EntryOrderDraft) -> str:
        if order.orderClass != "simple":
            return order.orderClass.upper()
        return {
            "market": "MKT",
            "limit": "LMT",
            "stop": "STOP",
            "stop_limit": "STPLMT",
        }[order.orderType]

    def _validate_stop(self, entry: float, stop_price: float, side: str = "buy") -> None:
        if side == "sell":
            if stop_price <= entry:
                raise ValueError("Stop price must be above entry for short positions")
        else:
            if stop_price >= entry:
                raise ValueError("Stop price must be below entry")
        if abs(stop_price - entry) >= entry * 0.5:
            raise ValueError("Stop price is too far from entry")

    def _validate_stop_mode(self, stop_mode: int, stop_modes: list[StopMode]) -> None:
        if stop_mode not in {1, 2, 3}:
            raise ValueError("Stop mode must be 1, 2, or 3")
        if len(stop_modes) < stop_mode:
            raise ValueError("Stop mode configuration is incomplete")

    def _validate_tranche_modes(self, tranche_count: int, tranche_modes: list[TrancheMode]) -> None:
        if tranche_count not in {1, 2, 3}:
            raise ValueError("Tranche count must be 1, 2, or 3")
        if len(tranche_modes) < tranche_count:
            raise ValueError("Profit tranche configuration is incomplete")

    def _reject_duplicate_active_stops(self, db: Session, symbol: str) -> None:
        self._cancel_stale_active_orders(db, symbol)
        active = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == symbol,
                OrderEntity.type == "STOP",
                OrderEntity.status.in_(["ACTIVE", "MODIFIED"]),
            )
        ).all()
        if active:
            raise ValueError("Active stop orders already exist for this symbol")

    def _reject_duplicate_active_order(
        self, db: Session, symbol: str, tranche_id: str, order_type: str
    ) -> None:
        self._cancel_stale_active_orders(db, symbol)
        active = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == symbol,
                OrderEntity.type == order_type,
                OrderEntity.status.in_(["ACTIVE", "MODIFIED"]),
            )
        ).all()
        if any(
            tranche_id in (order.covered_tranches or []) or order.tranche_label == tranche_id
            for order in active
        ):
            raise ValueError(f"Active {order_type} order already exists for {tranche_id}")

    def _cancel_stale_active_orders(self, db: Session, symbol: str) -> None:
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol))
        if (
            position is not None
            and position.phase != "closed"
            and any(tranche["status"] == "active" for tranche in position.tranches)
        ):
            return
        stale_orders = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == symbol,
                OrderEntity.status.in_(["ACTIVE", "MODIFIED"]),
            )
        ).all()
        if not stale_orders:
            return
        for order in stale_orders:
            order.status = "CANCELED"
        db.flush()

    def _cancel_broker_exit_orders(self, db: Session, symbol: str, order_types: set[str]) -> None:
        active_orders = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == symbol,
                OrderEntity.type.in_(list(order_types)),
                OrderEntity.status.in_(["ACTIVE", "MODIFIED"]),
            )
        ).all()
        for order in active_orders:
            if order.broker_order_id:
                self.broker.cancel_order(order.broker_order_id)
            order.status = "CANCELED"
        if active_orders:
            db.flush()

    def _reconcile_canceled_root_orders(self, db: Session, local_orders: list[OrderEntity]) -> None:
        for local in local_orders:
            if local.parent_id is not None:
                continue
            position = db.scalar(
                select(PositionEntity).where(PositionEntity.symbol == local.symbol)
            )
            if position is None or position.root_order_id != local.order_id:
                continue
            if position.phase != "entry_pending":
                continue
            position.phase = "closed"
            position.closed_at = utcnow()
            position.updated_at = utcnow()
            position.tranches = [
                {**tranche, "status": "canceled"} for tranche in deepcopy(position.tranches)
            ]
            siblings = db.scalars(
                select(OrderEntity).where(OrderEntity.symbol == local.symbol)
            ).all()
            for sibling in siblings:
                if sibling.status in {"ACTIVE", "MODIFIED", "PENDING", "ACCEPTED"}:
                    sibling.status = "CANCELED"
            db.flush()

    def _mark_entry_filled_if_ready(self, db: Session, position: PositionEntity) -> None:
        if position.phase != "entry_pending":
            return
        root_order = db.scalar(
            select(OrderEntity).where(OrderEntity.order_id == position.root_order_id)
        )
        if root_order is None:
            return
        position.phase = "trade_entered"
        root_order.status = "FILLED"
        root_order.filled_at = root_order.filled_at or utcnow()
        root_order.fill_price = root_order.fill_price or position.entry_price
        position.updated_at = utcnow()
        db.flush()

    def _require_position(self, db: Session, symbol: str) -> PositionEntity:
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol.upper()))
        if position is None:
            raise ValueError(f"No position for {symbol.upper()}")
        return position

    def _ensure_position_is_open(self, position: PositionEntity) -> None:
        if position.phase == "closed":
            raise ValueError(f"Position {position.symbol} is already closed")
        if not any(tranche["status"] == "active" for tranche in position.tranches):
            raise ValueError(f"No active tranches remain for {position.symbol}")

    def _ensure_position_filled(self, position: PositionEntity, message: str) -> None:
        if position.phase == "entry_pending":
            raise ValueError(message)

    def _ensure_profit_actionable(self, position: PositionEntity) -> None:
        self._ensure_position_is_open(position)
        self._ensure_position_filled(
            position, "Position management is unavailable until the entry order is filled."
        )
        if position.phase not in {"protected", "P1_done", "P2_done", "runner_only"}:
            raise ValueError(
                "Profit execution requires a protected or active profit-managed position"
            )

    def _effective_account_mode(self, requested_mode: str) -> str:
        if requested_mode == "alpaca_live" and self._live_disabled_reason(requested_mode):
            return "paper"
        return requested_mode

    def _live_disabled_reason(self, requested_mode: str) -> str | None:
        if requested_mode != "alpaca_live":
            return None
        if not self.settings.allow_live_trading:
            return "Live trading is disabled by config"
        if not self.settings.live_confirmation_token:
            return "Live confirmation token is not configured"
        return None

    async def _broadcast_position_bundle(
        self, db: Session, view: PositionView, pnl: float | None = None
    ) -> None:
        latest_log = self._latest_log_entry(db, view.symbol)
        await self.ws_manager.broadcast(
            "cockpit",
            self._event(
                "position_update",
                symbol=view.symbol,
                phase=view.phase,
                pnl=self._pnl(view) if pnl is None else pnl,
                position=view.model_dump(mode="json"),
            ),
        )
        await self.ws_manager.broadcast(
            "cockpit",
            self._event(
                "order_update",
                symbol=view.symbol,
                rootOrderId=view.rootOrderId,
                orders=[order.model_dump(mode="json") for order in view.orders],
            ),
        )
        if latest_log is not None:
            await self.ws_manager.broadcast(
                "cockpit",
                self._event(
                    "log_update", symbol=view.symbol, log=latest_log.model_dump(mode="json")
                ),
            )

    def _latest_log_entry(self, db: Session, symbol: str | None = None) -> LogEntry | None:
        stmt = select(TradeLogEntity)
        if symbol is not None:
            stmt = stmt.where((TradeLogEntity.symbol == symbol) | (TradeLogEntity.symbol.is_(None)))
        row = db.scalar(stmt.order_by(desc(TradeLogEntity.created_at)))
        if row is None:
            return None
        return LogEntry.model_validate(row, from_attributes=True)

    def _event(self, event_type: str, **payload: object) -> dict[str, object]:
        return {
            "type": event_type,
            "version": "2026-03-21",
            "timestamp": utcnow().isoformat(),
            **payload,
        }

    def _next_order_id(self, db: Session) -> str:
        persisted_max = 0
        for order_id in db.scalars(select(OrderEntity.order_id)):
            if not order_id.startswith("ORD-"):
                continue
            try:
                persisted_max = max(persisted_max, int(order_id.split("-", 1)[1]))
            except ValueError:
                continue
        pending_max = 0
        for instance in db.new:
            if isinstance(instance, OrderEntity) and instance.order_id.startswith("ORD-"):
                try:
                    pending_max = max(pending_max, int(instance.order_id.split("-", 1)[1]))
                except ValueError:
                    continue
        next_seq = max(persisted_max, pending_max) + 1
        return f"ORD-{next_seq:04d}"

    def _order_view(
        self,
        row: OrderEntity,
        broker_payload: dict | None = None,
        position_side: str = "buy",
    ) -> OrderView:
        filled_qty = (
            self._broker_filled_qty(broker_payload)
            if broker_payload
            else (row.orig_qty if row.filled_at else 0)
        )
        remaining_qty = self._broker_remaining_qty(
            broker_payload, row.qty, row.orig_qty, filled_qty
        )
        side = self._broker_side(broker_payload) or self._local_order_side(row, position_side)
        status = (
            str(broker_payload.get("status", row.status)).upper() if broker_payload else row.status
        )
        price = self._broker_price(broker_payload, row.price) if broker_payload else row.price
        return OrderView(
            id=row.order_id,
            symbol=row.symbol,
            side=side,
            type=row.type,
            qty=row.qty,
            origQty=row.orig_qty,
            filledQty=filled_qty,
            remainingQty=remaining_qty,
            price=price,
            status=status,
            tranche=row.tranche_label,
            coveredTranches=list(row.covered_tranches or []),
            parentId=row.parent_id,
            brokerOrderId=row.broker_order_id,
            cancelable=(
                self._broker_order_cancelable(broker_payload)
                if broker_payload
                else row.status in {"ACTIVE", "MODIFIED", "PENDING"}
            ),
            createdAt=row.created_at,
            updatedAt=(
                self._broker_timestamp(broker_payload, "updated_at")
                if broker_payload
                else row.filled_at or row.created_at
            ),
            filledAt=row.filled_at,
            fillPrice=(
                self._broker_fill_price(broker_payload, row.fill_price)
                if broker_payload
                else row.fill_price
            ),
        )

    def _broker_order_view(self, broker_payload: dict) -> OrderView:
        order_id = str(
            broker_payload.get("client_order_id") or broker_payload.get("id") or "BROKER"
        )
        qty = self._broker_qty(broker_payload)
        filled_qty = self._broker_filled_qty(broker_payload)
        remaining_qty = max(0, qty - filled_qty)
        return OrderView(
            id=order_id,
            symbol=str(broker_payload.get("symbol") or ""),
            side=self._broker_side(broker_payload),
            type=str(broker_payload.get("type") or "").upper(),
            qty=qty,
            origQty=qty,
            filledQty=filled_qty,
            remainingQty=remaining_qty,
            price=self._broker_price(broker_payload, 0.0),
            status=str(broker_payload.get("status") or "").upper(),
            tranche="BROKER",
            coveredTranches=[],
            parentId=None,
            brokerOrderId=str(broker_payload.get("id") or ""),
            cancelable=self._broker_order_cancelable(broker_payload),
            createdAt=self._broker_timestamp(broker_payload, "created_at"),
            updatedAt=self._broker_timestamp(broker_payload, "updated_at"),
            filledAt=self._broker_timestamp(broker_payload, "filled_at"),
            fillPrice=self._broker_fill_price(broker_payload, None),
        )

    def _position_view(self, db: Session, row: PositionEntity) -> PositionView:
        orders = self.get_orders(db, row.symbol)
        committed_stop_labels = {
            order.tranche
            for order in orders
            if order.type == "STOP" and order.tranche.startswith("S")
        }
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
            stopMode=len(committed_stop_labels),
            trancheCount=row.tranche_count,
        )

    def _log(self, db: Session, symbol: str | None, tag: str, message: str) -> None:
        db.add(TradeLogEntity(symbol=symbol, tag=tag, message=message, created_at=utcnow()))

    def _pnl(self, position: PositionView) -> float:
        entry = float(position.setup.get("entry", 0.0))
        side = self._position_side(position)
        direction = -1 if side == "sell" else 1
        active_shares = sum(
            tranche.qty for tranche in position.tranches if tranche.status == "active"
        )
        return round((position.livePrice - entry) * direction * active_shares, 2)

    def _broker_timestamp(self, payload: dict | None, key: str) -> datetime | None:
        if not payload:
            return None
        raw = payload.get(key)
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def _broker_qty(self, payload: dict | None) -> int:
        if not payload:
            return 0
        try:
            return int(float(payload.get("qty") or 0))
        except (TypeError, ValueError):
            return 0

    def _broker_filled_qty(self, payload: dict | None) -> int:
        if not payload:
            return 0
        try:
            return int(float(payload.get("filled_qty") or 0))
        except (TypeError, ValueError):
            return 0

    def _broker_remaining_qty(
        self, payload: dict | None, qty: int, orig_qty: int, filled_qty: int
    ) -> int:
        if payload:
            try:
                return max(0, int(float(payload.get("qty") or qty)) - filled_qty)
            except (TypeError, ValueError):
                return max(0, qty - filled_qty)
        return 0 if filled_qty >= orig_qty else qty

    def _broker_price(self, payload: dict | None, fallback: float) -> float:
        if not payload:
            return fallback
        for key in ("limit_price", "stop_price", "trail_price", "notional"):
            value = payload.get(key)
            if value not in (None, ""):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return fallback

    def _broker_fill_price(self, payload: dict | None, fallback: float | None) -> float | None:
        if not payload:
            return fallback
        for key in ("filled_avg_price", "limit_price", "stop_price"):
            value = payload.get(key)
            if value not in (None, ""):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return fallback

    def _broker_side(self, payload: dict | None) -> str | None:
        if not payload:
            return None
        side = payload.get("side")
        return str(side).upper() if side else None

    def _local_order_side(self, row: OrderEntity, position_side: str = "buy") -> str:
        if row.parent_id is None:
            return position_side.upper()
        return self._exit_side(position_side).upper()

    def _broker_order_cancelable(self, payload: dict | None) -> bool:
        if not payload:
            return False
        status = str(payload.get("status") or "").lower()
        return status in {
            "new",
            "accepted",
            "pending_new",
            "partially_filled",
            "accepted_for_bidding",
            "stopped",
            "calculated",
        }
