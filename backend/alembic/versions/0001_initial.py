"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("buying_power", sa.Float(), nullable=False),
        sa.Column("risk_pct", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("daily_realized_pnl", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=False, unique=True),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("live_price", sa.Float(), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("stop_ref", sa.String(length=32), nullable=False),
        sa.Column("stop_price", sa.Float(), nullable=False),
        sa.Column("tranche_count", sa.Integer(), nullable=False),
        sa.Column("tranche_modes", sa.JSON(), nullable=False),
        sa.Column("stop_modes", sa.JSON(), nullable=False),
        sa.Column("tranches", sa.JSON(), nullable=False),
        sa.Column("setup_snapshot", sa.JSON(), nullable=False),
        sa.Column("root_order_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("broker_order_id", sa.String(length=128), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("orig_qty", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("tranche_label", sa.String(length=64), nullable=False),
        sa.Column("covered_tranches", sa.JSON(), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fill_price", sa.Float(), nullable=True),
    )
    op.create_table(
        "trade_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=True),
        sa.Column("tag", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("trade_log")
    op.drop_table("orders")
    op.drop_table("positions")
    op.drop_table("account_settings")
