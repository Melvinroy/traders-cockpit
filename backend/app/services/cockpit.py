from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from math import floor
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.adapters.broker import (
    AlpacaBrokerAdapter,
    BrokerEntryOrder,
    BrokerWebhookEvent,
    PaperBrokerAdapter,
)
from app.adapters.market_data import AlpacaPolygonMarketDataAdapter, SetupMarketData
from app.core.config import Settings
from app.core.observability import get_request_id
from app.models.entities import (
    AccountSettingsEntity,
    AccountSnapshotEntity,
    BrokerFillEntity,
    BrokerOrderEntity,
    EventLogEntity,
    OrderEntity,
    OrderIntentEntity,
    PositionEntity,
    PositionProjectionEntity,
    ReconcileRunEntity,
    TradeLogEntity,
)
from app.schemas.cockpit import (
    AccountSettingsUpdate,
    AccountSettingsView,
    EntryOrderDraft,
    LogEntry,
    OrderFillView,
    OrderView,
    PositionView,
    ProfitRequest,
    SetupResponse,
    StopMode,
    StopsRequest,
    TradeEnterRequest,
    TradePreviewRequest,
    TradePreviewResponse,
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

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12]}"

    def _record_event(
        self,
        db: Session,
        event_type: str,
        *,
        symbol: str | None = None,
        intent_id: str | None = None,
        broker_order_id: str | None = None,
        fill_id: str | None = None,
        source: str = "system",
        payload: dict | None = None,
    ) -> None:
        db.add(
            EventLogEntity(
                event_id=self._new_id("evt"),
                event_type=event_type,
                symbol=symbol,
                intent_id=intent_id,
                broker_order_id=broker_order_id,
                fill_id=fill_id,
                source=source,
                payload=payload or {},
                created_at=utcnow(),
            )
        )

    def _record_external_event(
        self,
        db: Session,
        event: BrokerWebhookEvent,
    ) -> bool:
        if self._event_already_recorded(db, event.event_id):
            return False
        db.add(
            EventLogEntity(
                event_id=event.event_id,
                event_type=event.event_type,
                symbol=event.symbol,
                intent_id=(
                    self._lookup_intent_id(db, event.broker_order_id)
                    if event.broker_order_id
                    else None
                ),
                broker_order_id=event.broker_order_id,
                fill_id=event.fill_id,
                source="webhook",
                payload=event.payload or event.account_payload or {},
                created_at=event.occurred_at or utcnow(),
            )
        )
        return True

    def _event_already_recorded(self, db: Session, event_id: str) -> bool:
        if not event_id:
            return False
        if any(
            isinstance(instance, EventLogEntity) and instance.event_id == event_id
            for instance in db.new
        ):
            return True
        return (
            db.scalar(select(EventLogEntity).where(EventLogEntity.event_id == event_id)) is not None
        )

    def _upsert_intent(
        self,
        db: Session,
        *,
        intent_id: str,
        symbol: str,
        action: str,
        side: str,
        qty: int,
        price: float | None,
        status: str,
        blocking_reasons: list[str] | None = None,
        broker_order_id: str | None = None,
        payload: dict | None = None,
    ) -> OrderIntentEntity:
        intent = db.scalar(
            select(OrderIntentEntity).where(OrderIntentEntity.intent_id == intent_id)
        )
        if intent is None:
            intent = OrderIntentEntity(
                intent_id=intent_id,
                symbol=symbol,
                action=action,
                side=side,
                qty=qty,
                price=price,
                status=status,
                blocking_reasons=list(blocking_reasons or []),
                broker_order_id=broker_order_id,
                payload=payload or {},
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(intent)
        else:
            intent.status = status
            intent.blocking_reasons = list(blocking_reasons or [])
            intent.broker_order_id = broker_order_id
            intent.payload = payload or intent.payload
            intent.updated_at = utcnow()
        return intent

    def _sync_broker_order_snapshot(
        self,
        db: Session,
        *,
        broker_order_id: str | None,
        symbol: str,
        intent_id: str | None,
        payload: dict | None,
        fallback_status: str,
    ) -> None:
        if not broker_order_id:
            return
        snapshot = next(
            (
                instance
                for instance in db.new
                if isinstance(instance, BrokerOrderEntity)
                and instance.broker_order_id == broker_order_id
            ),
            None,
        )
        if snapshot is None:
            snapshot = db.scalar(
                select(BrokerOrderEntity).where(
                    BrokerOrderEntity.broker_order_id == broker_order_id
                )
            )
        status = (
            str(payload.get("status") or fallback_status).upper() if payload else fallback_status
        )
        qty = self._broker_qty(payload) if payload else 0
        filled_qty = self._broker_filled_qty(payload) if payload else 0
        remaining_qty = self._broker_remaining_qty(payload, qty, qty, filled_qty)
        avg_fill_price = self._broker_fill_price(payload, None) if payload else None
        if snapshot is None:
            snapshot = BrokerOrderEntity(
                broker_order_id=broker_order_id,
                symbol=symbol,
                broker=self.settings.broker_execution_provider,
                intent_id=intent_id,
                status=status,
                side=self._broker_side(payload),
                order_type=str(payload.get("type") or "").upper() if payload else None,
                qty=qty,
                filled_qty=filled_qty,
                remaining_qty=remaining_qty,
                avg_fill_price=avg_fill_price,
                raw_payload=payload or {},
                updated_at=utcnow(),
            )
            db.add(snapshot)
        else:
            snapshot.intent_id = intent_id
            snapshot.status = status
            snapshot.side = self._broker_side(payload)
            snapshot.order_type = (
                str(payload.get("type") or "").upper() if payload else snapshot.order_type
            )
            snapshot.qty = qty
            snapshot.filled_qty = filled_qty
            snapshot.remaining_qty = remaining_qty
            snapshot.avg_fill_price = avg_fill_price
            snapshot.raw_payload = payload or snapshot.raw_payload
            snapshot.updated_at = utcnow()

    def _record_fill(
        self,
        db: Session,
        *,
        fill_id: str,
        broker_order_id: str | None,
        symbol: str,
        intent_id: str | None,
        qty: int,
        price: float,
        occurred_at: datetime,
        payload: dict | None = None,
    ) -> None:
        existing = db.scalar(select(BrokerFillEntity).where(BrokerFillEntity.fill_id == fill_id))
        if existing is not None:
            return
        db.add(
            BrokerFillEntity(
                fill_id=fill_id,
                broker_order_id=broker_order_id,
                symbol=symbol,
                intent_id=intent_id,
                qty=qty,
                price=price,
                occurred_at=occurred_at,
                raw_payload=payload or {},
                created_at=utcnow(),
            )
        )

    def _sync_account_snapshot(
        self,
        db: Session,
        *,
        mode: str,
        equity: float,
        buying_power: float,
        cash: float | None,
        payload: dict | None = None,
    ) -> None:
        db.add(
            AccountSnapshotEntity(
                broker=self.settings.broker_execution_provider,
                mode=mode,
                equity=equity,
                buying_power=buying_power,
                cash=cash,
                payload=payload or {},
                recorded_at=utcnow(),
            )
        )

    def _sync_projection(self, db: Session, position: PositionEntity) -> None:
        db.flush()
        projection = self._projection_for_symbol(db, position.symbol)
        payload = self._projection_payload(db, position)
        if projection is None:
            projection = PositionProjectionEntity(
                symbol=position.symbol,
                phase=position.phase,
                reconcile_status=position.reconcile_status,
                projection_version=position.projection_version,
                payload=payload,
                updated_at=utcnow(),
                last_reconciled_at=position.last_reconciled_at,
            )
            db.add(projection)
        else:
            projection.phase = position.phase
            projection.reconcile_status = position.reconcile_status
            projection.projection_version = position.projection_version
            projection.payload = payload
            projection.updated_at = utcnow()
            projection.last_reconciled_at = position.last_reconciled_at

    def _start_reconcile_run(self, db: Session, trigger: str) -> ReconcileRunEntity:
        run = ReconcileRunEntity(
            run_id=self._new_id("rec"),
            trigger=trigger,
            broker=self.settings.broker_execution_provider,
            status="RUNNING",
            processed_orders=0,
            processed_fills=0,
            created_at=utcnow(),
        )
        db.add(run)
        return run

    def _finish_reconcile_run(
        self,
        run: ReconcileRunEntity,
        *,
        processed_orders: int,
        processed_fills: int,
        error: str | None = None,
    ) -> None:
        run.status = "FAILED" if error else "COMPLETED"
        run.processed_orders = processed_orders
        run.processed_fills = processed_fills
        run.error = error
        run.completed_at = utcnow()

    def _order_fills(self, db: Session, broker_order_id: str | None) -> list[OrderFillView]:
        if not broker_order_id:
            return []
        rows = db.scalars(
            select(BrokerFillEntity)
            .where(BrokerFillEntity.broker_order_id == broker_order_id)
            .order_by(BrokerFillEntity.occurred_at.asc())
        ).all()
        return [
            OrderFillView(
                id=row.fill_id,
                brokerOrderId=row.broker_order_id,
                symbol=row.symbol,
                qty=row.qty,
                price=row.price,
                occurredAt=row.occurred_at,
                intentId=row.intent_id,
            )
            for row in rows
        ]

    def _position_fills(self, db: Session, symbol: str) -> list[OrderFillView]:
        rows = db.scalars(
            select(BrokerFillEntity)
            .where(BrokerFillEntity.symbol == symbol)
            .order_by(BrokerFillEntity.occurred_at.asc())
        ).all()
        return [
            OrderFillView(
                id=row.fill_id,
                brokerOrderId=row.broker_order_id,
                symbol=row.symbol,
                qty=row.qty,
                price=row.price,
                occurredAt=row.occurred_at,
                intentId=row.intent_id,
            )
            for row in rows
        ]

    def rebuild_position_projections(
        self, db: Session, symbols: list[str] | None = None
    ) -> list[str]:
        requested = [symbol.upper() for symbol in symbols] if symbols else None
        stmt = select(PositionEntity).order_by(PositionEntity.symbol.asc())
        if requested:
            stmt = stmt.where(PositionEntity.symbol.in_(requested))
        positions = db.scalars(stmt).all()
        rebuilt_symbols: list[str] = []
        for position in positions:
            self._sync_projection(db, position)
            rebuilt_symbols.append(position.symbol)
        projection_stmt = select(PositionProjectionEntity)
        if requested:
            projection_stmt = projection_stmt.where(PositionProjectionEntity.symbol.in_(requested))
        for projection in db.scalars(projection_stmt).all():
            if projection.symbol not in rebuilt_symbols:
                db.delete(projection)
        db.flush()
        return rebuilt_symbols

    def next_reconcile_interval_seconds(self, db: Session) -> int:
        return (
            self.settings.reconcile_fast_interval_seconds
            if self._has_working_orders(db)
            else self.settings.reconcile_slow_interval_seconds
        )

    def run_reconcile_heartbeat(self, db: Session) -> None:
        self._reconcile_all_positions(db)
        self.get_account(db)
        db.commit()

    def _has_working_orders(self, db: Session) -> bool:
        working = db.scalar(
            select(OrderEntity.id).where(
                OrderEntity.status.in_(["ACTIVE", "MODIFIED", "PENDING", "ACCEPTED", "NEW"])
            )
        )
        if working is not None:
            return True
        return (
            db.scalar(
                select(PositionEntity.id).where(
                    PositionEntity.phase.in_(["entry_pending", "closing", "protected"])
                )
            )
            is not None
        )

    def _latest_reconcile_run(self, db: Session) -> ReconcileRunEntity | None:
        return db.scalar(
            select(ReconcileRunEntity)
            .where(ReconcileRunEntity.completed_at.is_not(None))
            .order_by(desc(ReconcileRunEntity.completed_at))
        )

    def _reconcile_health(
        self,
        db: Session,
        *,
        symbol: str | None = None,
        position: PositionEntity | None = None,
    ) -> tuple[str, datetime | None, list[str]]:
        symbol = symbol.upper() if symbol else None
        if position is None and symbol:
            position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol))
        latest_run = self._latest_reconcile_run(db)
        timestamps = [
            self._coerce_utc(timestamp)
            for timestamp in [
                position.last_reconciled_at if position is not None else None,
                latest_run.completed_at if latest_run is not None else None,
            ]
            if timestamp is not None
        ]
        last_reconciled_at = max(timestamps) if timestamps else None
        reasons: list[str] = []
        if self.settings.broker_execution_provider != "paper":
            if latest_run is None or last_reconciled_at is None:
                reasons.append("Reconciliation heartbeat is unavailable.")
            elif latest_run.status == "FAILED":
                reasons.append("Reconciliation heartbeat is failing.")
            elif (
                utcnow() - last_reconciled_at
            ).total_seconds() > self.settings.max_reconcile_age_seconds:
                reasons.append("Reconciliation is stale and execution is blocked.")
        if (
            position is not None
            and position.reconcile_status == "pending"
            and self.settings.broker_execution_provider != "paper"
        ):
            reasons.append(f"{position.symbol} is awaiting broker reconciliation.")
        if any("stale" in reason.lower() or "failing" in reason.lower() for reason in reasons):
            return "stale", last_reconciled_at, self._distinct_reasons(reasons)
        if reasons:
            return "pending", last_reconciled_at, self._distinct_reasons(reasons)
        if position is not None and position.reconcile_status == "pending":
            return "pending", last_reconciled_at, []
        return "synchronized", last_reconciled_at or utcnow(), []

    def _account_execution_blocking_reasons(
        self, db: Session, account: AccountSettingsEntity
    ) -> tuple[list[str], str, datetime | None]:
        reconcile_status, last_reconciled_at, reconcile_reasons = self._reconcile_health(db)
        reasons: list[str] = list(reconcile_reasons)
        if not self.settings.trading_enabled:
            reasons.append("Trading is disabled by runtime configuration.")
        if (
            account.mode in {"alpaca_paper", "alpaca_live"}
            and not self.settings.has_alpaca_credentials
        ):
            reasons.append("Broker credentials are missing for the configured execution mode.")
        return self._distinct_reasons(reasons), reconcile_status, last_reconciled_at

    def _pre_intent_blocking_reasons(
        self,
        db: Session,
        *,
        symbol: str,
        setup: SetupResponse | None = None,
        entry: float | None = None,
        shares: int | None = None,
        allow_active_intent: bool = False,
    ) -> list[str]:
        reasons = list(setup.executionBlockingReasons) if setup is not None else []
        if not allow_active_intent:
            reasons.extend(self._active_intent_blocking_reasons(db, symbol))
        if entry is not None and shares is not None:
            reasons.extend(self._entry_risk_blocking_reasons(db, symbol, entry, shares))
        return self._distinct_reasons(reasons)

    def _active_intent_blocking_reasons(self, db: Session, symbol: str) -> list[str]:
        active_intent = db.scalar(
            select(OrderIntentEntity).where(
                OrderIntentEntity.symbol == symbol.upper(),
                OrderIntentEntity.status.in_(
                    ["intent_accepted", "broker_accepted", "partially_filled"]
                ),
            )
        )
        if active_intent is None:
            return []
        return ["Another trade intent is already pending for this symbol."]

    def _entry_risk_blocking_reasons(
        self, db: Session, symbol: str, entry: float, shares: int
    ) -> list[str]:
        account = self.get_account(db)
        reasons: list[str] = []
        if entry * shares > account.equity * (self.settings.max_position_notional_pct / 100):
            reasons.append("Position exceeds max notional cap")
        if account.daily_realized_pnl < -(
            account.equity * (self.settings.daily_loss_limit_pct / 100)
        ):
            reasons.append("Daily loss limit reached")
        open_positions = db.scalars(
            select(PositionEntity).where(PositionEntity.phase != "closed")
        ).all()
        if any(position.symbol == symbol.upper() for position in open_positions):
            reasons.append(f"An open position already exists for {symbol.upper()}.")
        elif len(open_positions) >= self.settings.max_open_positions:
            reasons.append("Max open positions reached")
        self._cancel_stale_active_orders(db, symbol)
        active_orders = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == symbol.upper(),
                OrderEntity.status.in_(["ACTIVE", "MODIFIED"]),
            )
        ).all()
        if active_orders:
            reasons.append("Duplicate active orders exist for this symbol")
        return reasons

    @staticmethod
    def _distinct_reasons(reasons: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for reason in reasons:
            normalized = reason.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
        return unique

    @staticmethod
    def _coerce_utc(timestamp: datetime | None) -> datetime | None:
        if timestamp is None:
            return None
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

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
        blocking_reasons, reconcile_status, last_reconciled_at = (
            self._account_execution_blocking_reasons(db, account)
        )
        self._sync_account_snapshot(
            db,
            mode=account.mode,
            equity=equity,
            buying_power=buying_power,
            cash=cash,
            payload={"equity_source": equity_source},
        )
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
            reconcile_status=reconcile_status,
            last_reconciled_at=self._coerce_utc(last_reconciled_at),
            reconcileStatus=reconcile_status,
            lastReconciledAt=self._coerce_utc(last_reconciled_at),
            isExecutable=not blocking_reasons,
            executionBlockingReasons=blocking_reasons,
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
            self._log(
                db,
                None,
                "sys",
                f"Account settings updated: equity {payload.equity:.2f}",
            )
            db.commit()
        return self.get_account(db)

    def ingest_broker_webhook(self, db: Session, payload: dict) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ValueError("Webhook payload must be a JSON object.")
        normalized_events = self.broker.normalize_webhook_payload(payload)
        if not normalized_events:
            normalized_events = self._normalize_fallback_webhook_payload(payload)
        symbols: set[str] = set()
        processed_orders = 0
        processed_fills = 0
        processed_accounts = 0
        account_changed = False
        run = self._start_reconcile_run(db, "webhook")
        try:
            for event in normalized_events:
                if not self._record_external_event(db, event):
                    continue
                if event.kind == "order" and event.payload is not None:
                    symbol = str(event.symbol or "").upper()
                    broker_order_id = str(event.broker_order_id or "").strip()
                    if symbol and broker_order_id:
                        symbols.add(symbol)
                        processed_orders += 1
                        if event.fill_id:
                            processed_fills += 1
                        self._sync_broker_order_snapshot(
                            db,
                            broker_order_id=broker_order_id,
                            symbol=symbol,
                            intent_id=self._lookup_intent_id(db, broker_order_id),
                            payload=event.payload,
                            fallback_status=str(event.payload.get("status") or "PENDING").upper(),
                        )
                        position = db.scalar(
                            select(PositionEntity).where(PositionEntity.symbol == symbol)
                        )
                        if position is not None:
                            self._reconcile_position(db, position, {broker_order_id: event.payload})
                if event.kind == "account" and event.account_payload is not None:
                    equity = self._safe_float(event.account_payload.get("equity"))
                    buying_power = self._safe_float(event.account_payload.get("buying_power"))
                    cash = self._safe_float(event.account_payload.get("cash"))
                    if equity is not None and buying_power is not None:
                        processed_accounts += 1
                        account_changed = True
                        self._sync_account_snapshot(
                            db,
                            mode=self.settings.broker_mode,
                            equity=equity,
                            buying_power=buying_power,
                            cash=cash,
                            payload=event.account_payload,
                        )
            self._finish_reconcile_run(
                run,
                processed_orders=processed_orders,
                processed_fills=processed_fills,
            )
        except Exception as exc:
            self._finish_reconcile_run(
                run,
                processed_orders=processed_orders,
                processed_fills=processed_fills,
                error=str(exc),
            )
            raise
        return {
            "received": len(normalized_events),
            "processedOrders": processed_orders,
            "processedFills": processed_fills,
            "processedAccounts": processed_accounts,
            "symbols": sorted(symbols),
            "accountChanged": account_changed,
        }

    def get_setup(self, db: Session, symbol: str) -> SetupResponse:
        account = self.get_account(db)
        market = self.market_data.get_setup_data(symbol)
        position = db.scalar(select(PositionEntity).where(PositionEntity.symbol == symbol.upper()))
        reconcile_status, last_reconciled_at, reconcile_reasons = self._reconcile_health(
            db, symbol=symbol, position=position
        )
        return self._build_setup_response(
            market,
            account.equity,
            account.buying_power,
            account.risk_pct,
            account.equity_source,
            account.cash,
            reconcile_status=reconcile_status,
            last_reconciled_at=last_reconciled_at,
            additional_blocking_reasons=reconcile_reasons,
        )

    def preview_trade(self, db: Session, payload: TradePreviewRequest) -> TradePreviewResponse:
        setup = self.get_setup(db, payload.symbol)
        blocking_reasons = list(setup.executionBlockingReasons)
        preview_entry = round(setup.entry, 2)
        side = payload.order.side
        self._validate_stop(preview_entry, payload.stopPrice, side)
        per_share_risk = self._per_share_risk(preview_entry, payload.stopPrice, side)
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
            f"Preview: {payload.symbol.upper()} {side.upper()} {shares} sh LMT GTC @ {preview_entry:.2f} stop {payload.stopPrice:.2f}",
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
            isExecutable=setup.isExecutable,
            blockingReasons=blocking_reasons,
        )

    async def enter_trade(self, db: Session, payload: TradeEnterRequest) -> PositionView:
        symbol = payload.symbol.upper()
        setup = self.get_setup(db, symbol)
        order = payload.order
        preview_entry = round(setup.entry, 2)
        self._validate_stop(preview_entry, payload.stopPrice, order.side)
        self._validate_tranche_modes(payload.trancheCount, payload.trancheModes)
        per_share_risk = self._per_share_risk(preview_entry, payload.stopPrice, order.side)
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
        blocking_reasons = self._pre_intent_blocking_reasons(
            db,
            symbol=symbol,
            setup=setup,
            entry=preview_entry,
            shares=shares,
        )
        if blocking_reasons:
            raise ValueError("; ".join(blocking_reasons))
        qtys = self._split_shares(shares, payload.trancheCount, payload.trancheModes)
        intent_id = self._new_id("intent")
        session_state = setup.sessionState
        enforce_alpaca_offhours = setup.executionProvider == "alpaca_paper"
        entry_message: str
        broker_status = "PENDING"
        root_order_type = self._local_entry_order_type(order)
        order_for_broker = self._build_broker_entry_order(
            symbol, shares, preview_entry, order, session_state, enforce_alpaca_offhours
        )
        broker = self.broker.place_entry_order(order_for_broker)
        broker_status = broker.status or "PENDING"
        entry_filled = self._entry_should_start_filled(
            order_for_broker, broker_status, session_state, enforce_alpaca_offhours
        )
        if enforce_alpaca_offhours and session_state != "regular_open":
            broker_status = "PENDING"
            entry_filled = False
        if session_state != "regular_open":
            entry_message = "Midpoint limit order accepted and waiting for a regular-session fill."
        else:
            entry_message = (
                f"Trade entered: {order_for_broker.side.upper()} {shares} sh {symbol} {order_for_broker.order_type.upper()} "
                f"{order_for_broker.time_in_force.upper()} @ {preview_entry:.2f}"
            )
        intent_status = "filled" if entry_filled else "broker_accepted"
        self._upsert_intent(
            db,
            intent_id=intent_id,
            symbol=symbol,
            action="enter",
            side=order.side,
            qty=shares,
            price=preview_entry,
            status=intent_status,
            broker_order_id=broker.broker_order_id,
            payload={
                "request": payload.model_dump(mode="json"),
                "setup": setup.model_dump(mode="json"),
            },
        )
        self._record_event(
            db,
            "OrderIntentCreated",
            symbol=symbol,
            intent_id=intent_id,
            payload={"action": "enter", "qty": shares, "price": preview_entry},
        )
        self._record_event(
            db,
            (
                "BrokerOrderAccepted"
                if broker_status not in {"REJECTED", "ERROR"}
                else "BrokerOrderRejected"
            ),
            symbol=symbol,
            intent_id=intent_id,
            broker_order_id=broker.broker_order_id,
            payload=broker.payload or {"status": broker_status},
        )
        self._sync_broker_order_snapshot(
            db,
            broker_order_id=broker.broker_order_id,
            symbol=symbol,
            intent_id=intent_id,
            payload=broker.payload,
            fallback_status=broker_status,
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
                    "markState": ("frozen" if setup.sessionState != "regular_open" else "live"),
                    "markLabel": (
                        "Frozen outside regular session."
                        if setup.sessionState != "regular_open"
                        else None
                    ),
                },
                root_order_id=root_order_id,
                last_intent_id=intent_id,
                projection_version=1,
                reconcile_status="synchronized" if entry_filled else "pending",
                last_reconciled_at=utcnow() if entry_filled else None,
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
                "markState": ("frozen" if setup.sessionState != "regular_open" else "live"),
                "markLabel": (
                    "Frozen outside regular session."
                    if setup.sessionState != "regular_open"
                    else None
                ),
            }
            position.root_order_id = root_order_id
            position.last_intent_id = intent_id
            position.projection_version += 1
            position.reconcile_status = "synchronized" if entry_filled else "pending"
            position.last_reconciled_at = utcnow() if entry_filled else position.last_reconciled_at
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
                intent_id=intent_id,
                tranche_label=symbol,
                covered_tranches=[],
                parent_id=None,
                created_at=utcnow(),
                filled_at=utcnow() if entry_filled else None,
                fill_price=preview_entry if entry_filled else None,
                filled_qty=shares if entry_filled else 0,
            )
        )
        if entry_filled:
            self._record_fill(
                db,
                fill_id=self._new_id("fill"),
                broker_order_id=broker.broker_order_id,
                symbol=symbol,
                intent_id=intent_id,
                qty=shares,
                price=preview_entry,
                occurred_at=utcnow(),
                payload=broker.payload,
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
        self._sync_projection(db, position)
        db.commit()
        view = self.get_position(db, symbol)
        await self._broadcast_position_bundle(db, view, pnl=0.0)
        return view

    async def apply_stops(self, db: Session, payload: StopsRequest) -> PositionView:
        position = self._require_position(db, payload.symbol)
        self._ensure_position_is_open(position)
        self._ensure_position_filled(
            position,
            "Protective orders are unavailable until the entry order is filled.",
        )
        setup = self.get_setup(db, position.symbol)
        blocking_reasons = self._pre_intent_blocking_reasons(
            db,
            symbol=position.symbol,
            setup=setup,
        )
        if blocking_reasons:
            raise ValueError("; ".join(blocking_reasons))
        self._validate_stop_mode(payload.stopMode, payload.stopModes)
        self._reject_duplicate_active_stops(db, position.symbol)
        position_side = self._position_side(position)
        exit_side = self._exit_side(position_side)
        stop_range = abs(round(position.entry_price - position.stop_price, 2))
        current_tranches = deepcopy(position.tranches)
        for index, group in enumerate(self._stop_groups(current_tranches, payload.stopMode)):
            config = payload.stopModes[index]
            pct = self._default_stop_pct(config, index, payload.stopMode)
            price = (
                position.entry_price
                if config.mode == "be"
                else self._stop_price_from_pct(position.entry_price, stop_range, pct, position_side)
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
        position.projection_version += 1
        position.reconcile_status = "pending"
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
        self._sync_projection(db, position)
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    async def execute_profit_plan(self, db: Session, payload: ProfitRequest) -> PositionView:
        position = self._require_position(db, payload.symbol)
        self._ensure_profit_actionable(position)
        setup = self.get_setup(db, position.symbol)
        blocking_reasons = self._pre_intent_blocking_reasons(
            db,
            symbol=position.symbol,
            setup=setup,
        )
        if blocking_reasons:
            raise ValueError("; ".join(blocking_reasons))
        self._validate_tranche_modes(position.tranche_count, payload.trancheModes)
        tranches = deepcopy(position.tranches)
        position_side = self._position_side(position)
        exit_side = self._exit_side(position_side)
        per_share_risk = abs(round(position.entry_price - position.stop_price, 2))
        phase = position.phase
        executed_count = 0
        latest_intent_id = position.last_intent_id
        self._cancel_broker_exit_orders(db, position.symbol, {"STOP"})
        for index, tranche in enumerate(tranches):
            if tranche["status"] != "active":
                continue
            mode = payload.trancheModes[index]
            if mode.mode == "runner":
                intent_id = self._new_id("intent")
                latest_intent_id = intent_id
                self._reject_duplicate_active_order(db, position.symbol, tranche["id"], "TRAIL")
                runner_stop = self._trail_stop(
                    position.live_price, mode.trail, mode.trailUnit, position_side
                )
                tranche["mode"] = "runner"
                tranche["runnerStop"] = runner_stop
                broker = self.broker.place_trailing_stop(
                    position.symbol,
                    tranche["qty"],
                    mode.trail,
                    mode.trailUnit,
                    side=exit_side,
                )
                self._upsert_intent(
                    db,
                    intent_id=intent_id,
                    symbol=position.symbol,
                    action="runner",
                    side=exit_side,
                    qty=tranche["qty"],
                    price=runner_stop,
                    status="broker_accepted",
                    broker_order_id=broker.broker_order_id,
                    payload={"tranche": tranche["id"], "mode": mode.model_dump()},
                )
                self._record_event(
                    db,
                    "OrderIntentCreated",
                    symbol=position.symbol,
                    intent_id=intent_id,
                    payload={"action": "runner", "tranche": tranche["id"]},
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
                        intent_id=intent_id,
                        tranche_label=tranche["id"],
                        covered_tranches=[tranche["id"]],
                        parent_id=position.root_order_id,
                        created_at=utcnow(),
                        filled_qty=0,
                    )
                )
                self._sync_broker_order_snapshot(
                    db,
                    broker_order_id=broker.broker_order_id,
                    symbol=position.symbol,
                    intent_id=intent_id,
                    payload=broker.payload,
                    fallback_status=broker.status,
                )
                phase = "runner_only"
            else:
                intent_id = self._new_id("intent")
                latest_intent_id = intent_id
                self._reject_duplicate_active_order(db, position.symbol, tranche["id"], "LMT")
                target = self._resolve_target_price(
                    position.entry_price, per_share_risk, mode, position_side
                )
                broker = self.broker.place_limit_order(
                    position.symbol, tranche["qty"], target, side=exit_side
                )
                is_filled = str(broker.status or "").upper() == "FILLED"
                self._upsert_intent(
                    db,
                    intent_id=intent_id,
                    symbol=position.symbol,
                    action="take_profit",
                    side=exit_side,
                    qty=tranche["qty"],
                    price=target,
                    status="filled" if is_filled else "broker_accepted",
                    broker_order_id=broker.broker_order_id,
                    payload={"tranche": tranche["id"], "mode": mode.model_dump()},
                )
                self._record_event(
                    db,
                    "OrderIntentCreated",
                    symbol=position.symbol,
                    intent_id=intent_id,
                    payload={"action": "take_profit", "tranche": tranche["id"]},
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
                        status="FILLED" if is_filled else "ACTIVE",
                        intent_id=intent_id,
                        tranche_label=tranche["id"],
                        covered_tranches=[],
                        parent_id=position.root_order_id,
                        created_at=utcnow(),
                        filled_at=utcnow() if is_filled else None,
                        fill_price=target if is_filled else None,
                        filled_qty=tranche["qty"] if is_filled else 0,
                    )
                )
                self._sync_broker_order_snapshot(
                    db,
                    broker_order_id=broker.broker_order_id,
                    symbol=position.symbol,
                    intent_id=intent_id,
                    payload=broker.payload,
                    fallback_status=broker.status,
                )
                tranche["target"] = target
                tranche["exitOrderType"] = "LMT"
                if is_filled:
                    tranche["status"] = "sold"
                    tranche["exitPrice"] = target
                    tranche["exitFilledAt"] = utcnow().isoformat()
                    tranche["filledQty"] = tranche["qty"]
                    tranche["remainingQty"] = 0
                    self._record_fill(
                        db,
                        fill_id=self._new_id("fill"),
                        broker_order_id=broker.broker_order_id,
                        symbol=position.symbol,
                        intent_id=intent_id,
                        qty=tranche["qty"],
                        price=target,
                        occurred_at=utcnow(),
                        payload=broker.payload,
                    )
                    self._reduce_stop_orders(db, position.symbol, tranche["id"], tranche["qty"])
                    phase = "P1_done" if index == 0 else "P2_done"
                    executed_count += 1
                else:
                    tranche["status"] = "pending_exit"
                    tranche["filledQty"] = 0
                    tranche["remainingQty"] = tranche["qty"]
        phase = self._phase_from_tranches(position, tranches)
        position.tranches = tranches
        position.tranche_modes = [item.model_dump() for item in payload.trancheModes]
        position.phase = phase
        position.last_intent_id = latest_intent_id
        position.projection_version += 1
        position.reconcile_status = (
            "pending"
            if any(
                tranche["status"] in {"pending_exit", "partially_filled"} for tranche in tranches
            )
            else "synchronized"
        )
        position.last_reconciled_at = (
            utcnow() if position.reconcile_status == "synchronized" else position.last_reconciled_at
        )
        position.closed_at = utcnow() if phase == "closed" else None
        position.updated_at = utcnow()
        if executed_count == 0 and phase == "runner_only":
            raise ValueError("No executable profit tranches remain; runner already active")
        self._log(
            db,
            position.symbol,
            "exec",
            f"\u2713 Profit plan executed \u2014 {executed_count} tranche(s) filled",
        )
        self._sync_projection(db, position)
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    async def move_to_be(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        self._ensure_position_is_open(position)
        self._ensure_position_filled(
            position,
            "Protective orders are unavailable until the entry order is filled.",
        )
        setup = self.get_setup(db, position.symbol)
        blocking_reasons = self._pre_intent_blocking_reasons(
            db,
            symbol=position.symbol,
            setup=setup,
        )
        if blocking_reasons:
            raise ValueError("; ".join(blocking_reasons))
        position.tranches = [
            (
                {**tranche, "stop": position.entry_price}
                if tranche["status"] == "active"
                else tranche
            )
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
        position.projection_version += 1
        position.reconcile_status = "pending"
        position.updated_at = utcnow()
        self._log(
            db,
            position.symbol,
            "warn",
            f"All stops \u2192 breakeven: {position.entry_price:.2f}",
        )
        self._sync_projection(db, position)
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    async def flatten(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        self._ensure_position_is_open(position)
        setup = self.get_setup(db, position.symbol)
        blocking_reasons = self._pre_intent_blocking_reasons(
            db,
            symbol=position.symbol,
            setup=setup,
            allow_active_intent=(position.phase == "entry_pending"),
        )
        if blocking_reasons:
            raise ValueError("; ".join(blocking_reasons))
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
            position.projection_version += 1
            position.reconcile_status = "synchronized"
            position.last_reconciled_at = utcnow()
            position.updated_at = utcnow()
            self._log(db, position.symbol, "close", "Pending entry canceled before fill.")
            self._sync_projection(db, position)
            db.commit()
            view = self.get_position(db, position.symbol)
            await self._broadcast_position_bundle(db, view)
            return view
        updated_tranches = []
        broker_result = self.broker.close_position(position.symbol)
        is_filled = str(broker_result.status or "").upper() == "FILLED"
        for order in db.scalars(select(OrderEntity).where(OrderEntity.symbol == position.symbol)):
            if order.status in {"ACTIVE", "MODIFIED"}:
                if order.broker_order_id:
                    self.broker.cancel_order(order.broker_order_id)
                order.status = "CANCELED"
        for tranche in deepcopy(position.tranches):
            if tranche["status"] == "active":
                intent_id = self._new_id("intent")
                self._upsert_intent(
                    db,
                    intent_id=intent_id,
                    symbol=position.symbol,
                    action="flatten",
                    side=self._exit_side(self._position_side(position)),
                    qty=tranche["qty"],
                    price=position.live_price,
                    status="filled" if is_filled else "broker_accepted",
                    broker_order_id=broker_result.broker_order_id,
                    payload={"tranche": tranche["id"], "action": "flatten"},
                )
                db.add(
                    OrderEntity(
                        order_id=self._next_order_id(db),
                        broker_order_id=broker_result.broker_order_id,
                        symbol=position.symbol,
                        type="MKT",
                        qty=tranche["qty"],
                        orig_qty=tranche["qty"],
                        price=position.live_price,
                        status="FILLED" if is_filled else "ACTIVE",
                        intent_id=intent_id,
                        tranche_label=tranche["id"],
                        covered_tranches=[],
                        parent_id=position.root_order_id,
                        created_at=utcnow(),
                        filled_at=utcnow() if is_filled else None,
                        fill_price=position.live_price if is_filled else None,
                        filled_qty=tranche["qty"] if is_filled else 0,
                    )
                )
                self._record_event(
                    db,
                    "OrderIntentCreated",
                    symbol=position.symbol,
                    intent_id=intent_id,
                    payload={"action": "flatten", "tranche": tranche["id"]},
                )
                self._sync_broker_order_snapshot(
                    db,
                    broker_order_id=broker_result.broker_order_id,
                    symbol=position.symbol,
                    intent_id=intent_id,
                    payload=broker_result.payload,
                    fallback_status=broker_result.status,
                )
                tranche["target"] = position.live_price
                tranche["exitOrderType"] = "MKT"
                if is_filled:
                    tranche["status"] = "sold"
                    tranche["exitPrice"] = position.live_price
                    tranche["exitFilledAt"] = utcnow().isoformat()
                    tranche["filledQty"] = tranche["qty"]
                    tranche["remainingQty"] = 0
                    self._record_fill(
                        db,
                        fill_id=self._new_id("fill"),
                        broker_order_id=broker_result.broker_order_id,
                        symbol=position.symbol,
                        intent_id=intent_id,
                        qty=tranche["qty"],
                        price=position.live_price,
                        occurred_at=utcnow(),
                        payload=broker_result.payload,
                    )
                else:
                    tranche["status"] = "pending_exit"
                    tranche["filledQty"] = 0
                    tranche["remainingQty"] = tranche["qty"]
            updated_tranches.append(tranche)
        position.tranches = updated_tranches
        position.phase = "closed" if is_filled else "closing"
        position.closed_at = utcnow() if is_filled else None
        position.projection_version += 1
        position.reconcile_status = "synchronized" if is_filled else "pending"
        position.last_reconciled_at = utcnow() if is_filled else position.last_reconciled_at
        position.updated_at = utcnow()
        self._log(
            db,
            position.symbol,
            "close",
            "\u2b1b POSITION FLATTENED \u2014 all tranches closed @ market",
        )
        self._sync_projection(db, position)
        db.commit()
        view = self.get_position(db, position.symbol)
        await self._broadcast_position_bundle(db, view)
        return view

    def _projection_for_symbol(self, db: Session, symbol: str) -> PositionProjectionEntity | None:
        pending = next(
            (
                instance
                for instance in db.new
                if isinstance(instance, PositionProjectionEntity)
                and instance.symbol == symbol.upper()
            ),
            None,
        )
        if pending is not None:
            return pending
        return db.scalar(
            select(PositionProjectionEntity).where(
                PositionProjectionEntity.symbol == symbol.upper()
            )
        )

    def _orders_for_position(
        self,
        db: Session,
        symbol: str,
        *,
        position: PositionEntity | None = None,
        reconcile: bool = True,
    ) -> list[OrderView]:
        if position is None:
            position = db.scalar(
                select(PositionEntity).where(PositionEntity.symbol == symbol.upper())
            )
        position_side = self._position_side(position) if position is not None else "buy"
        if position is not None and reconcile and self._reconcile_position(db, position):
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
        return [
            self._order_view(
                db,
                row,
                position_side=position_side,
            )
            for row in rows
        ]

    def _projection_payload(self, db: Session, position: PositionEntity) -> dict:
        orders = self._orders_for_position(db, position.symbol, position=position, reconcile=False)
        committed_stop_labels = {
            order.tranche
            for order in orders
            if order.type == "STOP" and order.tranche.startswith("S")
        }
        position_side = self._position_side(position)
        mark_state = (
            position.setup_snapshot.get("markState", "frozen")
            if position.setup_snapshot
            else "frozen"
        )
        mark_label = position.setup_snapshot.get("markLabel") if position.setup_snapshot else None
        intent = (
            db.scalar(
                select(OrderIntentEntity).where(
                    OrderIntentEntity.intent_id == position.last_intent_id
                )
            )
            if position.last_intent_id
            else None
        )
        root_order = (
            db.scalar(select(OrderEntity).where(OrderEntity.order_id == position.root_order_id))
            if position.root_order_id
            else None
        )
        view = PositionView(
            symbol=position.symbol,
            phase=position.phase,
            side=position_side,
            livePrice=position.live_price,
            markState="live" if mark_state == "live" else "frozen",
            markLabel=(str(mark_label) if mark_label else self._mark_label(str(mark_state))),
            setup=position.setup_snapshot,
            tranches=[Tranche.model_validate(item) for item in position.tranches],
            orders=orders,
            trancheModes=[TrancheMode.model_validate(item) for item in position.tranche_modes],
            stopModes=[StopMode.model_validate(item) for item in position.stop_modes],
            rootOrderId=position.root_order_id,
            stopMode=len(committed_stop_labels),
            trancheCount=position.tranche_count,
            intentId=position.last_intent_id,
            intentStatus=intent.status if intent is not None else None,
            brokerOrderId=(root_order.broker_order_id if root_order is not None else None),
            brokerStatus=root_order.status if root_order is not None else None,
            reconcileStatus=position.reconcile_status,
            blockingReasons=list(intent.blocking_reasons) if intent is not None else [],
            projectionVersion=position.projection_version,
            lastReconciledAt=self._coerce_utc(position.last_reconciled_at),
            fills=self._position_fills(db, position.symbol),
        )
        return view.model_dump(mode="json")

    def _position_view_from_state(self, db: Session, row: PositionEntity) -> PositionView:
        return PositionView.model_validate(self._projection_payload(db, row))

    def get_positions(self, db: Session) -> list[PositionView]:
        self._reconcile_all_positions(db)
        projections = db.scalars(
            select(PositionProjectionEntity).order_by(PositionProjectionEntity.updated_at.desc())
        ).all()
        views = [
            PositionView.model_validate(projection.payload)
            for projection in projections
            if isinstance(projection.payload, dict) and projection.payload
        ]
        projected_symbols = {view.symbol for view in views}
        positions = db.scalars(
            select(PositionEntity).order_by(PositionEntity.created_at.desc())
        ).all()
        for position in positions:
            if position.symbol in projected_symbols:
                continue
            views.append(self._position_view_from_state(db, position))
        return views

    def get_position(self, db: Session, symbol: str) -> PositionView:
        position = self._require_position(db, symbol)
        if self._reconcile_position(db, position):
            db.commit()
        projection = self._projection_for_symbol(db, position.symbol)
        if projection is not None and isinstance(projection.payload, dict) and projection.payload:
            return PositionView.model_validate(projection.payload)
        return self._position_view_from_state(db, position)

    def get_orders(self, db: Session, symbol: str) -> list[OrderView]:
        return self._orders_for_position(db, symbol, reconcile=True)

    def get_recent_orders(self, db: Session, limit: int = 50) -> list[OrderView]:
        broker_orders_by_symbol = self._recent_broker_orders_by_symbol(limit=max(limit, 100))
        self._reconcile_all_positions(db, broker_orders_by_symbol)
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
        position_side_by_symbol = {
            position.symbol: self._position_side(position)
            for position in db.scalars(select(PositionEntity)).all()
        }
        merged: list[OrderView] = []
        seen_broker_ids: set[str] = set()
        for row in rows:
            broker_payload = broker_orders.get(row.broker_order_id or "")
            if broker_payload is not None:
                seen_broker_ids.add(str(broker_payload.get("id")))
            merged.append(
                self._order_view(
                    db,
                    row,
                    broker_payload,
                    position_side=position_side_by_symbol.get(row.symbol, "buy"),
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
        refreshed = self.broker.get_order(broker_order_id) or {
            **broker_order,
            "status": "canceled",
        }
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
        position_side = "buy"
        if local is not None:
            position = db.scalar(
                select(PositionEntity).where(PositionEntity.symbol == local.symbol)
            )
            if position is not None:
                position_side = self._position_side(position)
        return (
            self._order_view(db, local, refreshed, position_side=position_side)
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
        self._refresh_live_mark(position)
        position.updated_at = utcnow()
        self._reconcile_position(db, position)
        db.commit()
        base = position.entry_price
        snapshot = dict(position.setup_snapshot or {})
        await self.ws_manager.broadcast(
            "cockpit",
            self._event(
                "price_update",
                symbol=position.symbol,
                bid=snapshot.get("bid", position.live_price),
                ask=snapshot.get("ask", position.live_price),
                last=position.live_price,
                delta=round(position.live_price - base, 2),
                delta_pct=(round(((position.live_price - base) / base) * 100, 2) if base else 0.0),
                markState=snapshot.get("markState", "frozen"),
                markLabel=snapshot.get("markLabel"),
            ),
        )
        view = self._position_view(db, position)
        await self._broadcast_position_bundle(db, view)

    def _refresh_live_mark(self, position: PositionEntity) -> None:
        snapshot = dict(position.setup_snapshot or {})
        entry_order = snapshot.get("entryOrder")
        next_state = "frozen"
        next_label = "Mark frozen at last valid price."

        try:
            market = self.market_data.get_setup_data(position.symbol)
        except ValueError:
            market = None

        if (
            market is not None
            and market.quote_state == "live_quote"
            and market.session_state == "regular_open"
            and market.last > 0
        ):
            position.live_price = round(market.last, 2)
            snapshot.update(
                {
                    "bid": market.bid,
                    "ask": market.ask,
                    "last": round(market.last, 2),
                    "quoteTimestamp": (
                        market.quote_timestamp.isoformat() if market.quote_timestamp else None
                    ),
                    "sessionState": market.session_state,
                    "quoteState": market.quote_state,
                }
            )
            next_state = "live"
            next_label = None
        elif market is not None:
            next_label = (
                "Mark frozen outside regular session."
                if market.session_state != "regular_open"
                else "Mark frozen because the latest quote is stale or unavailable."
            )

        snapshot["markState"] = next_state
        snapshot["markLabel"] = next_label
        if isinstance(entry_order, dict):
            snapshot["entryOrder"] = entry_order
        position.setup_snapshot = snapshot

    def _reconcile_all_positions(
        self,
        db: Session,
        broker_orders_by_symbol: dict[str, dict[str, dict]] | None = None,
    ) -> None:
        changed = False
        processed_orders = 0
        processed_fills = 0
        run = self._start_reconcile_run(db, "poll")
        for position in db.scalars(select(PositionEntity)).all():
            symbol_orders = None
            if broker_orders_by_symbol is not None:
                symbol_orders = broker_orders_by_symbol.get(position.symbol.upper(), {})
            processed_orders += len(symbol_orders or {})
            changed = self._reconcile_position(db, position, symbol_orders) or changed
            processed_fills += len(self._position_fills(db, position.symbol))
        self._finish_reconcile_run(
            run,
            processed_orders=processed_orders,
            processed_fills=processed_fills,
        )
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
        for broker_order_id, payload in symbol_orders.items():
            local_order = db.scalar(
                select(OrderEntity).where(OrderEntity.broker_order_id == broker_order_id)
            )
            self._sync_broker_order_snapshot(
                db,
                broker_order_id=broker_order_id,
                symbol=position.symbol,
                intent_id=local_order.intent_id if local_order is not None else None,
                payload=payload,
                fallback_status=str(payload.get("status") or "UNKNOWN").upper(),
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
                root_order.filled_qty = root_order.orig_qty
                position.reconcile_status = "synchronized"
                position.last_reconciled_at = utcnow()
                position.projection_version += 1
                self._record_fill(
                    db,
                    fill_id=self._new_id("fill"),
                    broker_order_id=root_order.broker_order_id,
                    symbol=position.symbol,
                    intent_id=root_order.intent_id,
                    qty=root_order.orig_qty,
                    price=root_order.fill_price or position.entry_price,
                    occurred_at=root_order.filled_at or utcnow(),
                    payload=root_payload,
                )
                self._record_event(
                    db,
                    "OrderFilled",
                    symbol=position.symbol,
                    intent_id=root_order.intent_id,
                    broker_order_id=root_order.broker_order_id,
                    payload={"status": "FILLED"},
                )
                changed = True
        exit_orders = db.scalars(
            select(OrderEntity).where(
                OrderEntity.symbol == position.symbol,
                OrderEntity.type.in_(["STOP", "TRAIL", "LMT", "MKT"]),
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
        if changed:
            position.last_reconciled_at = utcnow()
            position.reconcile_status = "synchronized"
            position.projection_version += 1
            self._sync_projection(db, position)
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
                "payload": broker_payload,
            }
        if order.status not in {"ACTIVE", "MODIFIED"}:
            return None
        if position.phase == "entry_pending":
            return None
        if self.settings.broker_execution_provider != "paper":
            return None
        position_side = self._position_side(position)
        if position_side == "buy" and position.live_price > order.price:
            return None
        if position_side == "sell" and position.live_price < order.price:
            return None
        return {
            "status": "FILLED",
            "fill_price": order.price,
            "filled_at": utcnow(),
            "filled_qty": order.orig_qty,
            "payload": None,
        }

    def _apply_exit_fill(
        self,
        db: Session,
        position: PositionEntity,
        order: OrderEntity,
        fill_details: dict[str, object],
    ) -> bool:
        active_ids = {
            tranche["id"]
            for tranche in position.tranches
            if tranche["status"] in {"active", "pending_exit", "partially_filled"}
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
            order.filled_qty = int(fill_details.get("filled_qty") or order.orig_qty)
            return True
        tranches = deepcopy(position.tranches)
        filled_at = fill_details["filled_at"]
        fill_price = float(fill_details["fill_price"])
        filled_qty = int(fill_details.get("filled_qty") or order.orig_qty)
        order_fill_id = self._new_id("fill")
        for tranche in tranches:
            if tranche["id"] not in covered or tranche["status"] not in {
                "active",
                "pending_exit",
                "partially_filled",
            }:
                continue
            partial_fill = filled_qty < order.orig_qty
            tranche["status"] = "partially_filled" if partial_fill else "sold"
            tranche["target"] = fill_price
            tranche["exitPrice"] = fill_price
            tranche["exitFilledAt"] = (
                filled_at.isoformat() if isinstance(filled_at, datetime) else str(filled_at)
            )
            tranche["exitOrderType"] = order.type
            tranche["filledQty"] = filled_qty
            tranche["remainingQty"] = max(0, order.orig_qty - filled_qty)
            if partial_fill:
                tranche["qty"] = max(0, tranche["qty"] - filled_qty)
        order.status = str(fill_details["status"])
        order.fill_price = fill_price
        order.filled_at = filled_at if isinstance(filled_at, datetime) else utcnow()
        order.filled_qty = filled_qty
        position.tranches = tranches
        position.phase = self._phase_from_tranches(position, tranches)
        position.updated_at = utcnow()
        if position.phase == "closed":
            position.closed_at = position.closed_at or utcnow()
        else:
            position.closed_at = None
        self._record_fill(
            db,
            fill_id=order_fill_id,
            broker_order_id=order.broker_order_id,
            symbol=position.symbol,
            intent_id=order.intent_id,
            qty=filled_qty,
            price=fill_price,
            occurred_at=order.filled_at or utcnow(),
            payload=(fill_details.get("payload") if isinstance(fill_details, dict) else None),
        )
        self._record_event(
            db,
            (
                "OrderPartiallyFilled"
                if str(fill_details["status"]).upper() == "PARTIALLY_FILLED"
                else "OrderFilled"
            ),
            symbol=position.symbol,
            intent_id=order.intent_id,
            broker_order_id=order.broker_order_id,
            fill_id=order_fill_id,
            payload={
                "order_type": order.type,
                "filled_qty": filled_qty,
                "fill_price": fill_price,
            },
        )
        verb = "Stop hit" if order.type == "STOP" else "Exit filled"
        self._log(
            db,
            position.symbol,
            "warn" if order.type == "STOP" else "exec",
            f"{verb}: {' · '.join(covered)} @ {fill_price:.2f}",
        )
        db.flush()
        return True

    def _phase_from_tranches(self, position: PositionEntity, tranches: list[dict]) -> str:
        actionable = [
            tranche
            for tranche in tranches
            if tranche["status"] in {"active", "pending_exit", "partially_filled"}
        ]
        if not actionable:
            return "closed"
        if any(tranche["status"] == "pending_exit" for tranche in tranches):
            return "closing"
        runner_active = any(tranche.get("mode") == "runner" for tranche in actionable)
        sold_count = sum(1 for tranche in tranches if tranche["status"] in {"sold", "closed"})
        if runner_active and len(actionable) == 1:
            return "runner_only"
        if sold_count >= 2:
            return "P2_done"
        if sold_count >= 1:
            return "P1_done"
        return "protected"

    def _build_setup_response(
        self,
        market: SetupMarketData,
        equity: float,
        buying_power: float,
        risk_pct: float,
        equity_source: str,
        cash: float | None = None,
        *,
        reconcile_status: str = "synchronized",
        last_reconciled_at: datetime | None = None,
        additional_blocking_reasons: list[str] | None = None,
    ) -> SetupResponse:
        entry = round((market.bid + market.ask) / 2, 2)
        lod_stop = round(market.lod, 2)
        atr_stop = round(max(0.01, entry - market.atr14), 2)
        hod_stop = round(market.hod, 2)
        short_atr_stop = round(entry + market.atr14, 2)
        lod_is_valid = lod_stop < entry
        atr_is_valid = 0 < atr_stop < entry
        hod_is_valid = hod_stop > entry
        short_atr_is_valid = short_atr_stop > entry
        stop_reference_default = "lod" if lod_is_valid else "manual"
        short_stop_reference_default = "lod" if hod_is_valid else "manual"
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
        quote_age_ms = self._quote_age_ms(market.quote_timestamp)
        blocking_reasons = self._setup_execution_blocking_reasons(market, quote_age_ms)
        if additional_blocking_reasons:
            blocking_reasons.extend(additional_blocking_reasons)
        blocking_reasons = self._distinct_reasons(blocking_reasons)
        is_executable = not blocking_reasons
        data_quality = self._data_quality(market, quote_age_ms, is_executable)
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
            dataQuality=data_quality,
            quoteAgeMs=quote_age_ms,
            reconcileStatus=(
                "stale" if not is_executable and reconcile_status != "pending" else reconcile_status
            ),
            lastReconciledAt=self._coerce_utc(last_reconciled_at),
            isExecutable=is_executable,
            executionBlockingReasons=blocking_reasons,
            stopReferenceDefault=stop_reference_default,
            shortStopReferenceDefault=short_stop_reference_default,
            lodIsValid=lod_is_valid,
            atrIsValid=atr_is_valid,
            hodIsValid=hod_is_valid,
            shortAtrIsValid=short_atr_is_valid,
            lodStop=lod_stop,
            atrStop=atr_stop,
            hodStop=hod_stop,
            shortAtrStop=short_atr_stop,
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

    def _quote_age_ms(self, quote_timestamp: datetime | None) -> int | None:
        if quote_timestamp is None:
            return None
        return max(0, int((utcnow() - quote_timestamp).total_seconds() * 1000))

    def _setup_execution_blocking_reasons(
        self, market: SetupMarketData, quote_age_ms: int | None
    ) -> list[str]:
        reasons: list[str] = []
        if not self.settings.trading_enabled:
            reasons.append("Trading is disabled by runtime configuration.")
        if market.symbol.upper() in self.settings.disabled_symbols:
            reasons.append(f"{market.symbol.upper()} is currently disabled for trading.")
        if quote_age_ms is None:
            reasons.append("Quote timestamp is unavailable.")
        elif quote_age_ms > self.settings.max_quote_age_seconds * 1000:
            reasons.append("Quote is stale and cannot be used for execution.")
        if self.settings.app_env not in {"development", "test"} and (
            market.fallback_reason or not market.quote_is_real or market.technicals_are_fallback
        ):
            reasons.append("Fallback-backed market data is visible but blocked from execution.")
        if (
            self.settings.broker_mode in {"alpaca_paper", "alpaca_live"}
            and not self.settings.has_alpaca_credentials
        ):
            reasons.append("Broker credentials are missing for the configured execution mode.")
        return reasons

    def _data_quality(
        self, market: SetupMarketData, quote_age_ms: int | None, is_executable: bool
    ) -> str:
        if not is_executable:
            return "blocked"
        if quote_age_ms is not None and quote_age_ms > self.settings.max_quote_age_seconds * 1000:
            return "stale"
        if market.fallback_reason or not market.quote_is_real or market.technicals_are_fallback:
            return "fallback"
        return "live"

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
        self, entry: float, per_share_risk: float, mode: TrancheMode, side: str
    ) -> float:
        if mode.target == "Manual" and mode.manualPrice is not None:
            return round(mode.manualPrice, 2)
        multiplier = {"1R": 1, "2R": 2, "3R": 3}[mode.target]
        direction = 1 if side == "buy" else -1
        return round(entry + direction * per_share_risk * multiplier, 2)

    def _trail_stop(self, live_price: float, trail: float, trail_unit: str, side: str) -> float:
        if side == "buy":
            return (
                round(live_price - trail, 2)
                if trail_unit == "$"
                else round(live_price * (1 - trail / 100), 2)
            )
        return (
            round(live_price + trail, 2)
            if trail_unit == "$"
            else round(live_price * (1 + trail / 100), 2)
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
                OrderEntity.symbol == symbol,
                OrderEntity.status.in_(["ACTIVE", "MODIFIED"]),
            )
        ).all()
        if active:
            raise ValueError("Duplicate active orders exist for this symbol")

    def _build_broker_entry_order(
        self,
        symbol: str,
        shares: int,
        entry: float,
        order: EntryOrderDraft,
        session_state: str,
        enforce_alpaca_offhours: bool,
    ) -> BrokerEntryOrder:
        return BrokerEntryOrder(
            symbol=symbol,
            qty=shares,
            side=order.side,
            order_type="limit",
            time_in_force="gtc",
            limit_price=round(entry, 2),
            reference_price=round(entry, 2),
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
        return False

    def _local_entry_order_type(self, order: EntryOrderDraft) -> str:
        return "LMT"

    def _per_share_risk(self, entry: float, stop_price: float, side: str) -> float:
        return round(entry - stop_price, 2) if side == "buy" else round(stop_price - entry, 2)

    def _stop_price_from_pct(self, entry: float, stop_range: float, pct: float, side: str) -> float:
        direction = -1 if side == "buy" else 1
        return round(entry + direction * stop_range * pct / 100.0, 2)

    def _position_side(self, position: PositionEntity) -> str:
        entry_order = position.setup_snapshot.get("entryOrder") if position.setup_snapshot else None
        side = entry_order.get("side") if isinstance(entry_order, dict) else None
        return "sell" if side == "sell" else "buy"

    def _exit_side(self, side: str) -> str:
        return "sell" if side == "buy" else "buy"

    def _mark_label(self, state: str, reason: str | None = None) -> str | None:
        if state == "live":
            return None
        return reason or "Mark frozen at last valid price."

    def _validate_stop(self, entry: float, stop_price: float, side: str) -> None:
        if side == "buy":
            if stop_price >= entry:
                raise ValueError("Stop price must be below entry")
            if stop_price <= entry * 0.5:
                raise ValueError("Stop price too far below entry")
            return
        if stop_price <= entry:
            raise ValueError("Stop price must be above entry for short entries")
        if stop_price >= entry * 1.5:
            raise ValueError("Stop price too far above entry")

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
        if not any(
            tranche["status"] in {"active", "pending_exit", "partially_filled"}
            for tranche in position.tranches
        ):
            raise ValueError(f"No active tranches remain for {position.symbol}")

    def _ensure_position_filled(self, position: PositionEntity, message: str) -> None:
        if position.phase == "entry_pending":
            raise ValueError(message)

    def _ensure_profit_actionable(self, position: PositionEntity) -> None:
        self._ensure_position_is_open(position)
        self._ensure_position_filled(
            position,
            "Position management is unavailable until the entry order is filled.",
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
                "position_projection_update",
                symbol=view.symbol,
                phase=view.phase,
                projectionVersion=view.projectionVersion,
                reconcileStatus=view.reconcileStatus,
                position=view.model_dump(mode="json"),
            ),
        )
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
                "intent_update",
                symbol=view.symbol,
                intentId=view.intentId,
                intentStatus=view.intentStatus,
                blockingReasons=view.blockingReasons,
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
        if view.fills:
            await self.ws_manager.broadcast(
                "cockpit",
                self._event(
                    "fill_update",
                    symbol=view.symbol,
                    fills=[fill.model_dump(mode="json") for fill in view.fills],
                ),
            )
        if latest_log is not None:
            await self.ws_manager.broadcast(
                "cockpit",
                self._event(
                    "log_update",
                    symbol=view.symbol,
                    log=latest_log.model_dump(mode="json"),
                ),
            )

    async def broadcast_position_projection(self, db: Session, view: PositionView) -> None:
        await self._broadcast_position_bundle(db, view)

    async def broadcast_account_update(self, db: Session) -> None:
        account = self.get_account(db)
        await self.ws_manager.broadcast(
            "cockpit",
            self._event(
                "account_update",
                account=account.model_dump(mode="json"),
                effectiveMode=account.effective_mode,
                reconcileStatus=account.reconcile_status,
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
        event: dict[str, object] = {
            "type": event_type,
            "version": "2026-03-21",
            "timestamp": utcnow().isoformat(),
            **payload,
        }
        request_id = get_request_id()
        if request_id:
            event["requestId"] = request_id
        return event

    def _lookup_intent_id(self, db: Session, broker_order_id: str) -> str | None:
        order = db.scalar(select(OrderEntity).where(OrderEntity.broker_order_id == broker_order_id))
        if order is not None:
            return order.intent_id
        snapshot = db.scalar(
            select(BrokerOrderEntity).where(BrokerOrderEntity.broker_order_id == broker_order_id)
        )
        return snapshot.intent_id if snapshot is not None else None

    def _normalize_fallback_webhook_payload(self, payload: dict) -> list[BrokerWebhookEvent]:
        raw_events = payload.get("events") if isinstance(payload.get("events"), list) else [payload]
        normalized: list[BrokerWebhookEvent] = []
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue
            order_payload = None
            for key in ("order", "data", "payload"):
                candidate = raw_event.get(key)
                if isinstance(candidate, dict) and candidate.get("id") and candidate.get("symbol"):
                    order_payload = candidate
                    break
            if order_payload is None and raw_event.get("id") and raw_event.get("symbol"):
                order_payload = raw_event
            account_payload = None
            for key in ("account", "account_snapshot"):
                candidate = raw_event.get(key)
                if isinstance(candidate, dict):
                    account_payload = candidate
                    break
            if (
                account_payload is None
                and raw_event.get("equity") is not None
                and raw_event.get("buying_power") is not None
            ):
                account_payload = raw_event
            event_type = str(
                raw_event.get("type")
                or raw_event.get("event")
                or raw_event.get("event_type")
                or "broker_webhook"
            ).lower()
            occurred_at = self._broker_timestamp(raw_event, "timestamp")
            if order_payload is not None:
                broker_order_id = str(order_payload.get("id") or "").strip() or None
                symbol = str(order_payload.get("symbol") or "").upper() or None
                event_id = self._stable_external_event_id(
                    "order", event_type, order_payload, occurred_at
                )
                fill_id = None
                status = str(order_payload.get("status") or "").lower()
                if status in {"filled", "partially_filled"}:
                    fill_id = self._stable_external_event_id(
                        "fill",
                        status,
                        {
                            "broker_order_id": broker_order_id,
                            "filled_qty": order_payload.get("filled_qty"),
                            "filled_at": order_payload.get("filled_at"),
                        },
                        occurred_at,
                    )
                normalized.append(
                    BrokerWebhookEvent(
                        event_id=event_id,
                        event_type=event_type,
                        kind="order",
                        broker_order_id=broker_order_id,
                        symbol=symbol,
                        payload=order_payload,
                        fill_id=fill_id,
                        occurred_at=occurred_at,
                    )
                )
            if account_payload is not None:
                normalized.append(
                    BrokerWebhookEvent(
                        event_id=self._stable_external_event_id(
                            "account", event_type, account_payload, occurred_at
                        ),
                        event_type=event_type,
                        kind="account",
                        payload=account_payload,
                        occurred_at=occurred_at,
                        account_payload=account_payload,
                    )
                )
        return normalized

    def _stable_external_event_id(
        self, kind: str, event_type: str, payload: dict, occurred_at: datetime | None
    ) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(
            f"{kind}|{event_type}|{occurred_at.isoformat() if occurred_at else ''}|{canonical}".encode()
        ).hexdigest()[:24]
        return f"external-{kind}-{digest}"

    @staticmethod
    def _safe_float(value: object) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

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
        db: Session,
        row: OrderEntity,
        broker_payload: dict | None = None,
        position_side: str = "buy",
    ) -> OrderView:
        intent = (
            db.scalar(select(OrderIntentEntity).where(OrderIntentEntity.intent_id == row.intent_id))
            if row.intent_id
            else None
        )
        fills = self._order_fills(db, row.broker_order_id)
        filled_qty = (
            self._broker_filled_qty(broker_payload)
            if broker_payload
            else (row.filled_qty if row.filled_qty else (row.orig_qty if row.filled_at else 0))
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
            intentId=row.intent_id,
            intentStatus=intent.status if intent is not None else None,
            brokerStatus=(
                str(broker_payload.get("status") or status).upper()
                if broker_payload
                else row.status
            ),
            reconcileStatus=(
                "synchronized" if fills or row.status in {"FILLED", "CANCELED"} else "pending"
            ),
            fills=fills,
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
            brokerStatus=str(broker_payload.get("status") or "").upper(),
            reconcileStatus="external_only",
            fills=[],
        )

    def _position_view(self, db: Session, row: PositionEntity) -> PositionView:
        projection = self._projection_for_symbol(db, row.symbol)
        if projection is not None and isinstance(projection.payload, dict) and projection.payload:
            return PositionView.model_validate(projection.payload)
        return self._position_view_from_state(db, row)

    def _log(self, db: Session, symbol: str | None, tag: str, message: str) -> None:
        db.add(TradeLogEntity(symbol=symbol, tag=tag, message=message, created_at=utcnow()))

    def _pnl(self, position: PositionView) -> float:
        entry = float(position.setup.get("entry", 0.0))
        active_shares = sum(
            tranche.qty for tranche in position.tranches if tranche.status == "active"
        )
        direction = 1 if position.side == "buy" else -1
        return round((position.livePrice - entry) * active_shares * direction, 2)

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

    def _local_order_side(self, row: OrderEntity, position_side: str) -> str:
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
