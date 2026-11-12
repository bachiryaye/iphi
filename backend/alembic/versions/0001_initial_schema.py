"""Initial schema: platform, monitor heartbeat, append-only audit log.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reused by later append-only tables (incident_event, incident_evidence; rules.md D-12).
REJECT_MUTATION_FUNCTION = """
CREATE FUNCTION iphi_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        "platform",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("environment = 'simulation'", name=op.f("ck_platform_environment_v1")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform")),
        sa.UniqueConstraint("key", name=op.f("uq_platform_key")),
    )

    op.create_table(
        "monitor_heartbeat",
        sa.Column("process", sa.String(32), nullable=False),
        sa.Column("last_cycle_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_cycle_duration_ms", sa.Integer(), nullable=False),
        sa.Column("cycle_lag_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'stopped')", name=op.f("ck_monitor_heartbeat_status")
        ),
        sa.CheckConstraint(
            "last_cycle_duration_ms >= 0",
            name=op.f("ck_monitor_heartbeat_duration_non_negative"),
        ),
        sa.CheckConstraint("cycle_lag_ms >= 0", name=op.f("ck_monitor_heartbeat_lag_non_negative")),
        sa.PrimaryKeyConstraint("process", name=op.f("pk_monitor_heartbeat")),
    )

    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("platform_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_label", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('allowed', 'denied', 'failed')", name=op.f("ck_audit_event_outcome")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_event")),
    )
    op.create_index(op.f("ix_audit_event_action"), "audit_event", ["action"])
    op.create_index(
        op.f("ix_audit_event_occurred_at"), "audit_event", [sa.literal_column("occurred_at DESC")]
    )

    op.execute(REJECT_MUTATION_FUNCTION)
    op.execute(
        "CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE ON audit_event "
        "FOR EACH ROW EXECUTE FUNCTION iphi_reject_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_event_append_only ON audit_event")
    op.execute("DROP FUNCTION iphi_reject_mutation()")
    op.drop_index(op.f("ix_audit_event_occurred_at"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_action"), table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_table("monitor_heartbeat")
    op.drop_table("platform")
