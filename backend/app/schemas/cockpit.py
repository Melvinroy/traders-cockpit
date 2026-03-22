from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StopMode(BaseModel):
    mode: Literal["stop", "be"] = "stop"
    pct: float | None = None


class TrancheMode(BaseModel):
    mode: Literal["limit", "runner"] = "limit"
    trail: float = 2.0
    trailUnit: Literal["$", "%"] = "$"
    target: Literal["1R", "2R", "3R", "Manual"] = "1R"
    manualPrice: float | None = None


class Tranche(BaseModel):
    id: str
    qty: int
    stop: float
    target: float | None = None
    status: Literal["active", "sold", "canceled"] = "active"
    mode: Literal["limit", "runner"] = "limit"
    trail: float = 2.0
    trailUnit: Literal["$", "%"] = "$"
    label: str
    runnerStop: float | None = None


class OrderView(BaseModel):
    id: str
    type: str
    qty: int
    origQty: int
    price: float
    status: str
    tranche: str
    coveredTranches: list[str] = Field(default_factory=list)
    parentId: str | None = None
    brokerOrderId: str | None = None
    createdAt: datetime | None = None
    filledAt: datetime | None = None
    fillPrice: float | None = None


class PositionView(BaseModel):
    symbol: str
    phase: str
    livePrice: float
    setup: dict
    tranches: list[Tranche]
    orders: list[OrderView]
    trancheModes: list[TrancheMode]
    stopModes: list[StopMode]
    rootOrderId: str | None = None
    stopMode: int = 0
    trancheCount: int = 3


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
    sessionState: Literal["regular_open", "overnight", "pre_market", "after_hours", "closed"] = "closed"
    quoteState: Literal["live_quote", "cached_quote", "quote_unavailable"] = "quote_unavailable"
    entryBasis: str = "midpoint"
    stopReferenceDefault: str = "lod"
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
    atrExtension: float
    extFrom10Ma: float


class TradePreviewRequest(BaseModel):
    symbol: str
    entry: float
    stopRef: Literal["lod", "atr", "manual"] = "lod"
    stopPrice: float
    riskPct: float


class TradeEnterRequest(BaseModel):
    symbol: str
    entry: float
    stopRef: Literal["lod", "atr", "manual"] = "lod"
    stopPrice: float
    trancheCount: int = 3
    trancheModes: list[TrancheMode]
    offHoursMode: Literal["queue_for_open", "extended_hours_limit"] | None = None


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
    risk_pct: float
    mode: str
    effective_mode: str
    daily_realized_pnl: float
    allow_live_trading: bool
    max_position_notional_pct: float
    daily_loss_limit_pct: float
    max_open_positions: int
    live_disabled_reason: str | None = None


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
