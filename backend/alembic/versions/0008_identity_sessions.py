"""Server-side identity and sessions (ADR 0007, ADR 0025).

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("role", sa.String(8), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('viewer', 'engineer', 'admin')", name="role"),
    )
    op.create_table(
        "user_session",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="expiry"),
    )
    op.create_index("ix_user_session_expires_at", "user_session", ["expires_at"])
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"])
    op.create_index(
        "ix_audit_event_login_time",
        "audit_event",
        ["occurred_at"],
        postgresql_where=sa.text("action = 'auth.login'"),
    )


def downgrade() -> None:
    op.drop_index("ix_audit_event_login_time", "audit_event")
    op.drop_table("user_session")
    op.drop_table("app_user")
