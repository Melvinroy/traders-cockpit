from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StopMode(BaseModel):
    mode: Literal["stop", "be"] = "stop"
    pct: float | None = None


EntrySide = Literal["buy", "sell"]


class EntryOrderDraft(BaseModel):
    side: EntrySide = "buy"


class TrancheMode(BaseModel):
    mode: Literal["limit", "runner"] = "limit"
    allocationPct: float | None = None
    trail: float = 2.0
    trailUnit: Literal["$", "%"] = "$"
    target: Literal["1R", "2R", "3R", "Manual"] = "1R"
    manualPrice: float | None = None


class Tranche(BaseModel):
    id: str
    qty: int
    stop: float
    target: float | None = None
    status: Literal["active", "pending_exit", "partially_filled", "sold", "closed", "canceled"] = (
        "active"
    )
    exitPrice: float | None = None
    exitFilledAt: datetime | None = None
    exitOrderType: str | None = None
    filledQty: int = 0
    remainingQty: int | None = None
    mode: Literal["limit", "runner"] = "limit"
    trail: float = 2.0
    trailUnit: Literal["$", "%"] = "$"
    label: str
    runnerStop: float | None = None


class OrderFillView(BaseModel):
    id: str
    brokerOrderId: str | None = None
    symbol: str
    qty: int
    price: float
    occurredAt: datetime
    intentId: str | None = None


class OrderView(BaseModel):
    id: str
    symbol: str
    side: str | None = None
    type: str
    qty: int
    origQty: int
    filledQty: int = 0
    remainingQty: int = 0
    price: float
    status: str
    tranche: str
    coveredTranches: list[str] = Field(default_factory=list)
    parentId: str | None = None
    brokerOrderId: str | None = None
    cancelable: bool = False
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    filledAt: datetime | None = None
    fillPrice: float | None = None
    intentId: str | None = None
    intentStatus: str | None = None
    brokerStatus: str | None = None
    reconcileStatus: str | None = None
    fills: list[OrderFillView] = Field(default_factory=list)


class PositionView(BaseModel):
    symbol: str
    phase: str
    side: EntrySide = "buy"
    livePrice: float
    markState: Literal["live", "frozen"] = "frozen"
    markLabel: str | None = None
    setup: dict
    tranches: list[Tranche]
    orders: list[OrderView]
    trancheModes: list[TrancheMode]
    stopModes: list[StopMode]
    rootOrderId: str | None = None
    stopMode: int = 0
    trancheCount: int = 3
    intentId: str | None = None
    intentStatus: str | None = None
    brokerOrderId: str | None = None
    brokerStatus: str | None = None
    reconcileStatus: str | None = None
    blockingReasons: list[str] = Field(default_factory=list)
    projectionVersion: int = 1
    lastReconciledAt: datetime | None = None
    fills: list[OrderFillView] = Field(default_factory=list)


class LogEntry(BaseModel):
    id: int
    symbol: str | None = None
    tag: str
    message: str
    created_at: datetime


class SetupResponse(BaseModel):
    symbol: str
    provider: str = "mock"
    providerState: str = "fallback_all"
    quoteProvider: str = "mock"
    technicalsProvider: str = "mock"
    executionProvider: str = "paper"
    quoteIsReal: bool = False
    technicalsAreFallback: bool = True
    fallbackReason: str | None = None
    quoteTimestamp: datetime | None = None
    sessionState: Literal["regular_open", "overnight", "pre_market", "after_hours", "closed"] = (
        "closed"
    )
    quoteState: Literal["live_quote", "cached_quote", "quote_unavailable"] = "quote_unavailable"
    entryBasis: str = "midpoint"
    dataQuality: Literal["live", "fallback", "stale", "blocked"] = "blocked"
    quoteAgeMs: int | None = None
    reconcileStatus: Literal["synchronized", "pending", "stale"] = "synchronized"
    lastReconciledAt: datetime | None = None
    isExecutable: bool = False
    executionBlockingReasons: list[str] = Field(default_factory=list)
    stopReferenceDefault: Literal["lod", "atr", "manual"] = "lod"
    shortStopReferenceDefault: Literal["lod", "atr", "manual"] = "lod"
    lodIsValid: bool = True
    atrIsValid: bool = True
    hodIsValid: bool = True
    shortAtrIsValid: bool = True
    lodStop: float
    atrStop: float
    hodStop: float
    shortAtrStop: float
    manualStopWarning: str | None = None
    bid: float
    ask: float
    last: float
    lod: float
    hod: float
    prev_close: float
    atr14: float
    sma10: float
    sma50: float
    sma200: float
    sma200_prev: float
    rvol: float
    days_to_cover: float
    entry: float
    finalStop: float
    r1: float
    r2: float
    r3: float
    shares: int
    dollarRisk: float
    perShareRisk: float
    riskPct: float
    accountEquity: float
    accountBuyingPower: float
    accountCash: float | None = None
    equitySource: str = "local_settings"
    sizingWarning: str | None = None
    buyingPowerNote: str | None = None
    atrExtension: float
    extFrom10Ma: float


class TradePreviewResponse(BaseModel):
    symbol: str
    entry: float
    finalStop: float
    perShareRisk: float
    shares: int
    dollarRisk: float
    sizingWarning: str | None = None
    isExecutable: bool = False
    blockingReasons: list[str] = Field(default_factory=list)


class TradePreviewRequest(BaseModel):
    symbol: str
    entry: float
    stopRef: Literal["lod", "atr", "manual"] = "lod"
    stopPrice: float
    riskPct: float
    order: EntryOrderDraft = Field(default_factory=EntryOrderDraft)


class TradeEnterRequest(BaseModel):
    symbol: str
    entry: float
    stopRef: Literal["lod", "atr", "manual"] = "lod"
    stopPrice: float
    trancheCount: int = 3
    trancheModes: list[TrancheMode]
    offHoursMode: Literal["queue_for_open", "extended_hours_limit"] | None = None
    order: EntryOrderDraft = Field(default_factory=EntryOrderDraft)


class StopsRequest(BaseModel):
    symbol: str
    stopMode: int
    stopModes: list[StopMode]


class ProfitRequest(BaseModel):
    symbol: str
    trancheModes: list[TrancheMode]


class MoveToBeRequest(BaseModel):
    symbol: str


class AccountSettingsView(BaseModel):
    equity: float
    buying_power: float
    cash: float | None = None
    risk_pct: float
    mode: str
    effective_mode: str
    equity_source: str = "local_settings"
    daily_realized_pnl: float
    allow_live_trading: bool
    max_position_notional_pct: float
    daily_loss_limit_pct: float
    max_open_positions: int
    live_disabled_reason: str | None = None
    reconcile_status: str = "synchronized"
    last_reconciled_at: datetime | None = None
    reconcileStatus: str = "synchronized"
    lastReconciledAt: datetime | None = None
    isExecutable: bool = True
    executionBlockingReasons: list[str] = Field(default_factory=list)


class AccountSettingsUpdate(BaseModel):
    equity: float
    risk_pct: float
    mode: Literal["paper", "alpaca_paper", "alpaca_live"]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str
    expires_at: str | None = None
