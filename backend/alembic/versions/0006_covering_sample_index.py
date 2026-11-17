"""Covering unique index on metric_sample for index-only series aggregates (ADR 0019).

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "uq_metric_sample_component_id_metric_name_observed_at_source"
KEY = "component_id, metric_name, observed_at, source"


def _replace(include: str) -> None:
    # Built aside, then attached: deduplication never lapses.
    op.execute(f"CREATE UNIQUE INDEX uq_metric_sample_next ON metric_sample ({KEY}){include}")
    op.execute(f"ALTER TABLE metric_sample DROP CONSTRAINT {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE metric_sample ADD CONSTRAINT {CONSTRAINT} UNIQUE USING INDEX "
        "uq_metric_sample_next"
    )


def upgrade() -> None:
    _replace(" INCLUDE (value, quality)")
    op.execute("ALTER TABLE metric_sample SET (autovacuum_vacuum_insert_scale_factor = 0.02)")


def downgrade() -> None:
    op.execute("ALTER TABLE metric_sample RESET (autovacuum_vacuum_insert_scale_factor)")
    _replace("")
