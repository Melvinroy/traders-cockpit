from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class AccountSettingsEntity(Base):
    __tablename__ = "account_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    buying_power: Mapped[float] = mapped_column(Float, nullable=False)
    risk_pct: Mapped[float] = mapped_column(Float, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    daily_realized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PositionEntity(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    live_price: Mapped[float] = mapped_column(Float, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_ref: Mapped[str] = mapped_column(String(32), nullable=False)
    stop_price: Mapped[float] = mapped_column(Float, nullable=False)
    tranche_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tranche_modes: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    stop_modes: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    tranches: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    setup_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    root_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrderEntity(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    orig_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    tranche_label: Mapped[str] = mapped_column(String(64), nullable=False)
    covered_tranches: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)


class TradeLogEntity(Base):
    __tablename__ = "trade_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tag: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
