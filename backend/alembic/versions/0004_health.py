"""Health rules, evaluations, hysteresis states and component and platform snapshots.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "health_rule",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=32), nullable=False),
        sa.Column("target_selector", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=True),
        sa.Column("aggregation", sa.String(length=16), nullable=True),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("operator", sa.String(length=8), nullable=True),
        sa.Column("warning_threshold", sa.Double(), nullable=True),
        sa.Column("critical_threshold", sa.Double(), nullable=True),
        sa.Column("warning_clear", sa.Double(), nullable=True),
        sa.Column("critical_clear", sa.Double(), nullable=True),
        sa.Column("raise_after", sa.SmallInteger(), nullable=False),
        sa.Column("clear_after", sa.SmallInteger(), nullable=False),
        sa.Column("min_samples", sa.SmallInteger(), nullable=False),
        sa.Column("rationale", sa.String(length=500), nullable=False),
        sa.Column("recommendation", sa.String(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(metric_name IS NULL) = (rule_type = 'absence') "
            "AND (metric_name IS NULL) = (aggregation IS NULL) "
            "AND (metric_name IS NULL) = (operator IS NULL)",
            name=op.f("ck_health_rule_measure_complete"),
        ),
        sa.CheckConstraint(
            "aggregation IS NULL OR aggregation IN ('last', 'avg', 'max', 'p95', 'sum', 'ratio')",
            name=op.f("ck_health_rule_aggregation"),
        ),
        sa.CheckConstraint(
            "failure_class IN ('availability', 'latency', 'freshness', 'errors', 'resources', "
            "'backlog', 'connectivity', 'telemetry_loss')",
            name=op.f("ck_health_rule_failure_class"),
        ),
        sa.CheckConstraint(
            "operator IS NULL OR operator IN ('gt', 'ge', 'lt')",
            name=op.f("ck_health_rule_operator"),
        ),
        sa.CheckConstraint(
            "rule_type IN ('threshold', 'freshness', 'absence', 'availability_ratio')",
            name=op.f("ck_health_rule_rule_type"),
        ),
        sa.CheckConstraint(
            "(warning_threshold IS NULL) = (warning_clear IS NULL) "
            "AND (critical_threshold IS NULL) = (critical_clear IS NULL)",
            name=op.f("ck_health_rule_levels_complete"),
        ),
        sa.CheckConstraint(
            "raise_after >= 1 AND clear_after >= 1 AND min_samples >= 1",
            name=op.f("ck_health_rule_counts_positive"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_health_rule_version_positive")),
        sa.CheckConstraint("window_seconds > 0", name=op.f("ck_health_rule_window_positive")),
        sa.ForeignKeyConstraint(
            ["metric_name"],
            ["metric_definition.metric_name"],
            name=op.f("fk_health_rule_metric_name_metric_definition"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_health_rule")),
        sa.UniqueConstraint("key", "version", name=op.f("uq_health_rule_key_version")),
    )
    op.create_table(
        "platform_health",
        sa.Column("platform_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("since", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_evaluated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=True),
        sa.Column("rationale", sa.String(length=512), nullable=False),
        sa.Column("decided_by", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.CheckConstraint(
            "state IN ('healthy', 'warning', 'unknown', 'critical')",
            name=op.f("ck_platform_health_state"),
        ),
        sa.CheckConstraint(
            "priority IS NULL OR priority BETWEEN 1 AND 4", name=op.f("ck_platform_health_priority")
        ),
        sa.ForeignKeyConstraint(
            ["platform_id"], ["platform.id"], name=op.f("fk_platform_health_platform_id_platform")
        ),
        sa.PrimaryKeyConstraint("platform_id", name=op.f("pk_platform_health")),
    )
    op.create_table(
        "rule_evaluation",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("evaluated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("window_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("observed_value", sa.Double(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("raw_state", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.String(length=512), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "raw_state IN ('healthy', 'warning', 'unknown', 'critical')",
            name=op.f("ck_rule_evaluation_raw_state"),
        ),
        sa.CheckConstraint(
            "state IN ('healthy', 'warning', 'unknown', 'critical')",
            name=op.f("ck_rule_evaluation_state"),
        ),
        sa.CheckConstraint(
            "sample_count >= 0", name=op.f("ck_rule_evaluation_sample_count_non_negative")
        ),
        sa.CheckConstraint(
            "window_start < evaluated_at", name=op.f("ck_rule_evaluation_window_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["component.id"],
            name=op.f("fk_rule_evaluation_component_id_component"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["health_rule.id"], name=op.f("fk_rule_evaluation_rule_id_health_rule")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_evaluation")),
        sa.UniqueConstraint(
            "component_id",
            "rule_id",
            "evaluated_at",
            name=op.f("uq_rule_evaluation_component_id_rule_id_evaluated_at"),
        ),
    )
    op.create_index(
        "ix_rule_evaluation_component_id_evaluated_at",
        "rule_evaluation",
        ["component_id", "evaluated_at"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_evaluated_at_id",
        "rule_evaluation",
        ["evaluated_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_rule_evaluation_rule_id_evaluated_at",
        "rule_evaluation",
        ["rule_id", "evaluated_at"],
        unique=False,
    )
    op.create_table(
        "component_health",
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("since", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_evaluated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("reason_evaluation_id", sa.BigInteger(), nullable=True),
        sa.Column("impacted_by", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.CheckConstraint(
            "state IN ('healthy', 'warning', 'unknown', 'critical')",
            name=op.f("ck_component_health_state"),
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["component.id"],
            name=op.f("fk_component_health_component_id_component"),
        ),
        sa.ForeignKeyConstraint(
            ["reason_evaluation_id"],
            ["rule_evaluation.id"],
            name=op.f("fk_component_health_reason_evaluation_id_rule_evaluation"),
        ),
        sa.PrimaryKeyConstraint("component_id", name=op.f("pk_component_health")),
    )
    op.create_table(
        "rule_state",
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(length=16), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("since", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("pending_state", sa.String(length=16), nullable=True),
        sa.Column("raw_streak", sa.SmallInteger(), nullable=False),
        sa.Column("raw_state", sa.String(length=16), nullable=False),
        sa.Column("observed_value", sa.Double(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.String(length=512), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_evaluated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_evaluation_id", sa.BigInteger(), nullable=False),
        sa.Column("state_evaluation_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "pending_state IS NULL "
            "OR pending_state IN ('healthy', 'warning', 'unknown', 'critical')",
            name=op.f("ck_rule_state_pending_state"),
        ),
        sa.CheckConstraint(
            "raw_state IN ('healthy', 'warning', 'unknown', 'critical')",
            name=op.f("ck_rule_state_raw_state"),
        ),
        sa.CheckConstraint(
            "state IN ('healthy', 'warning', 'unknown', 'critical')",
            name=op.f("ck_rule_state_state"),
        ),
        sa.CheckConstraint(
            "(pending_state IS NULL) = (raw_streak = 0)", name=op.f("ck_rule_state_streak_pending")
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["component.id"], name=op.f("fk_rule_state_component_id_component")
        ),
        sa.ForeignKeyConstraint(
            ["last_evaluation_id"],
            ["rule_evaluation.id"],
            name=op.f("fk_rule_state_last_evaluation_id_rule_evaluation"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["health_rule.id"], name=op.f("fk_rule_state_rule_id_health_rule")
        ),
        sa.ForeignKeyConstraint(
            ["state_evaluation_id"],
            ["rule_evaluation.id"],
            name=op.f("fk_rule_state_state_evaluation_id_rule_evaluation"),
        ),
        sa.PrimaryKeyConstraint("component_id", "rule_key", name=op.f("pk_rule_state")),
    )
    # Rule versions are immutable (D-08): a change is a new version, never an update.
    op.execute(
        "CREATE TRIGGER health_rule_immutable BEFORE UPDATE OR DELETE ON health_rule "
        "FOR EACH ROW EXECUTE FUNCTION iphi_reject_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER health_rule_immutable ON health_rule")
    op.drop_table("rule_state")
    op.drop_table("component_health")
    op.drop_index("ix_rule_evaluation_rule_id_evaluated_at", table_name="rule_evaluation")
    op.drop_index("ix_rule_evaluation_evaluated_at_id", table_name="rule_evaluation")
    op.drop_index("ix_rule_evaluation_component_id_evaluated_at", table_name="rule_evaluation")
    op.drop_table("rule_evaluation")
    op.drop_table("platform_health")
    op.drop_table("health_rule")
