"""auth storage tables

Revision ID: 0002_auth_storage
Revises: 0001_initial
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_auth_storage"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("password_salt", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_addr", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth_users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "revoked_at", "expires_at"],
    )
    op.create_table(
        "auth_login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_key", sa.String(length=160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_auth_login_attempts_subject_time",
        "auth_login_attempts",
        ["subject_key", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_auth_login_attempts_subject_time", table_name="auth_login_attempts")
    op.drop_table("auth_login_attempts")
    op.drop_index("idx_auth_sessions_user_active", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("auth_users")
