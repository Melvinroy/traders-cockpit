"""merge 0002 migration heads

Revision ID: 0003_merge_0002_heads
Revises: 0002_auth_storage, 0002_hedge_hardening_foundation
Create Date: 2026-08-27
"""

revision = "0003_merge_0002_heads"
down_revision = ("0002_auth_storage", "0002_hedge_hardening_foundation")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
