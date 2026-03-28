"""hedge hardening foundation

Revision ID: 0002_hedge_hardening_foundation
Revises: 0001_initial
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_hedge_hardening_foundation"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("last_intent_id", sa.String(length=64), nullable=True))
    op.add_column(
        "positions",
        sa.Column("projection_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "positions",
        sa.Column(
            "reconcile_status", sa.String(length=32), nullable=False, server_default="synchronized"
        ),
    )
    op.add_column(
        "positions", sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("filled_qty", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("orders", sa.Column("intent_id", sa.String(length=64), nullable=True))

    op.create_table(
        "event_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=True),
        sa.Column("intent_id", sa.String(length=64), nullable=True),
        sa.Column("broker_order_id", sa.String(length=128), nullable=True),
        sa.Column("fill_id", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "order_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intent_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocking_reasons", sa.JSON(), nullable=False),
        sa.Column("broker_order_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "broker_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("broker_order_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("broker", sa.String(length=32), nullable=False),
        sa.Column("intent_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=True),
        sa.Column("order_type", sa.String(length=32), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("filled_qty", sa.Integer(), nullable=False),
        sa.Column("remaining_qty", sa.Integer(), nullable=False),
        sa.Column("avg_fill_price", sa.Float(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "broker_fills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fill_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("broker_order_id", sa.String(length=128), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("intent_id", sa.String(length=64), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "position_projections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=False, unique=True),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("reconcile_status", sa.String(length=32), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "account_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("broker", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("buying_power", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "reconcile_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("broker", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("processed_orders", sa.Integer(), nullable=False),
        sa.Column("processed_fills", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.alter_column("positions", "projection_version", server_default=None)
    op.alter_column("positions", "reconcile_status", server_default=None)
    op.alter_column("orders", "filled_qty", server_default=None)


def downgrade() -> None:
    op.drop_table("reconcile_runs")
    op.drop_table("account_snapshots")
    op.drop_table("position_projections")
    op.drop_table("broker_fills")
    op.drop_table("broker_orders")
    op.drop_table("order_intents")
    op.drop_table("event_log")
    op.drop_column("orders", "intent_id")
    op.drop_column("orders", "filled_qty")
    op.drop_column("positions", "last_reconciled_at")
    op.drop_column("positions", "reconcile_status")
    op.drop_column("positions", "projection_version")
    op.drop_column("positions", "last_intent_id")
