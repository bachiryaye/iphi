"""LLM comparison reference and persistent actor budget (ADR 0021).

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_diagnostic_llm_provider_created_at",
        "diagnostic",
        ["provider", sa.text("created_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("kind = 'llm'"),
    )
    op.add_column("diagnostic", sa.Column("deterministic_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_diagnostic_deterministic_id_diagnostic",
        "diagnostic",
        "diagnostic",
        ["deterministic_id"],
        ["id"],
    )
    op.create_table(
        "diagnostic_budget",
        sa.Column("actor", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempts BETWEEN 1 AND 6", name="attempts_bounded"),
    )


def downgrade() -> None:
    op.drop_index("ix_diagnostic_llm_provider_created_at", "diagnostic")
    op.drop_table("diagnostic_budget")
    op.drop_constraint(
        "fk_diagnostic_deterministic_id_diagnostic", "diagnostic", type_="foreignkey"
    )
    op.drop_column("diagnostic", "deterministic_id")
