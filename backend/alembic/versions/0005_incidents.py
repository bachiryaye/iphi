"""Incidents, their evidence, timeline and impacts, and diagnostics.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# D-12: evidence, timeline, impacts and diagnostics are never updated nor deleted.
APPEND_ONLY = ("incident_evidence", "incident_event", "incident_impact", "diagnostic")


def upgrade() -> None:
    op.create_table(
        "incident",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("platform_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("failure_class", sa.String(length=32), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("peak_severity", sa.String(length=16), nullable=False),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolution", sa.String(length=16), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("reopen_count", sa.Integer(), nullable=False),
        sa.Column("scenario_run_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "(acknowledged_at IS NULL) = (acknowledged_by IS NULL) "
            "AND (status <> 'acknowledged' OR acknowledged_at IS NOT NULL)",
            name=op.f("ck_incident_acknowledgement_complete"),
        ),
        sa.CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL) "
            "AND (resolved_at IS NULL) = (resolved_by IS NULL) "
            "AND (resolved_at IS NULL) = (resolution IS NULL)",
            name=op.f("ck_incident_resolution_complete"),
        ),
        sa.CheckConstraint(
            "failure_class IN ('availability', 'latency', 'freshness', 'errors', 'resources', "
            "'backlog', 'connectivity', 'telemetry_loss')",
            name=op.f("ck_incident_failure_class"),
        ),
        sa.CheckConstraint(
            "peak_severity IN ('warning', 'critical')", name=op.f("ck_incident_peak_severity")
        ),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('auto_recovered', 'manual', 'reset')",
            name=op.f("ck_incident_resolution"),
        ),
        sa.CheckConstraint(
            "severity IN ('warning', 'critical')", name=op.f("ck_incident_severity")
        ),
        sa.CheckConstraint("source IN ('simulation', 'mqtt')", name=op.f("ck_incident_source")),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')", name=op.f("ck_incident_status")
        ),
        sa.CheckConstraint(
            "occurrence_count >= 1 AND reopen_count >= 0 AND last_seen_at >= opened_at",
            name=op.f("ck_incident_counts_consistent"),
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["component.id"], name=op.f("fk_incident_component_id_component")
        ),
        sa.ForeignKeyConstraint(
            ["platform_id"], ["platform.id"], name=op.f("fk_incident_platform_id_platform")
        ),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"],
            ["scenario_run.id"],
            name=op.f("fk_incident_scenario_run_id_scenario_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident")),
        sa.UniqueConstraint("number", name=op.f("uq_incident_number")),
    )
    op.create_index(
        "ix_incident_component_id_opened_at",
        "incident",
        ["component_id", sa.literal_column("opened_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_incident_fingerprint_resolved_at",
        "incident",
        ["fingerprint", "resolved_at"],
        unique=False,
    )
    op.create_index(
        "ix_incident_opened_at_number", "incident", ["opened_at", "number"], unique=False
    )
    op.create_index(
        "ix_incident_status_opened_at",
        "incident",
        ["status", sa.literal_column("opened_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_incident_fingerprint_active",
        "incident",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("status <> 'resolved'"),
    )
    op.create_table(
        "diagnostic",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("observed_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hypotheses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_set_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_redacted", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('deterministic', 'llm')", name=op.f("ck_diagnostic_kind")),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed', 'rejected')", name=op.f("ck_diagnostic_status")
        ),
        sa.CheckConstraint(
            "prompt_redacted IS NULL OR char_length(prompt_redacted) <= 32768",
            name=op.f("ck_diagnostic_prompt_bounded"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incident.id"], name=op.f("fk_diagnostic_incident_id_incident")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diagnostic")),
        sa.UniqueConstraint(
            "incident_id", "idempotency_key", name=op.f("uq_diagnostic_incident_id_idempotency_key")
        ),
    )
    op.create_index(
        "ix_diagnostic_incident_id_created_at",
        "diagnostic",
        ["incident_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "incident_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_label", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('system', 'user')", name=op.f("ck_incident_event_actor_type")
        ),
        sa.CheckConstraint(
            "event_type IN ('opened', 'occurrence', 'severity_changed', 'acknowledged', "
            "'commented', 'resolved', 'reopened', 'reclassified', 'downstream_suppressed', "
            "'diagnostic_added')",
            name=op.f("ck_incident_event_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incident.id"], name=op.f("fk_incident_event_incident_id_incident")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_event")),
    )
    op.create_index(
        "ix_incident_event_incident_id_occurred_at",
        "incident_event",
        ["incident_id", "occurred_at", "id"],
        unique=False,
    )
    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("metric_sample_id", sa.BigInteger(), nullable=True),
        sa.Column("log_event_id", sa.BigInteger(), nullable=True),
        sa.Column("rule_evaluation_id", sa.BigInteger(), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('trigger', 'supporting', 'impact', 'recovery')",
            name=op.f("ck_incident_evidence_role"),
        ),
        sa.CheckConstraint(
            "num_nonnulls(metric_sample_id, log_event_id, rule_evaluation_id) = 1",
            name=op.f("ck_incident_evidence_one_reference"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incident.id"], name=op.f("fk_incident_evidence_incident_id_incident")
        ),
        sa.ForeignKeyConstraint(
            ["log_event_id"],
            ["log_event.id"],
            name=op.f("fk_incident_evidence_log_event_id_log_event"),
        ),
        sa.ForeignKeyConstraint(
            ["metric_sample_id"],
            ["metric_sample.id"],
            name=op.f("fk_incident_evidence_metric_sample_id_metric_sample"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_evaluation_id"],
            ["rule_evaluation.id"],
            name=op.f("fk_incident_evidence_rule_evaluation_id_rule_evaluation"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_evidence")),
        sa.UniqueConstraint(
            "incident_id",
            "metric_sample_id",
            "log_event_id",
            "rule_evaluation_id",
            name="uq_incident_evidence_reference",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_incident_evidence_log_event_id",
        "incident_evidence",
        ["log_event_id"],
        unique=False,
        postgresql_where=sa.text("log_event_id IS NOT NULL"),
    )
    op.create_index(
        "ix_incident_evidence_metric_sample_id",
        "incident_evidence",
        ["metric_sample_id"],
        unique=False,
        postgresql_where=sa.text("metric_sample_id IS NOT NULL"),
    )
    op.create_index(
        "ix_incident_evidence_rule_evaluation_id",
        "incident_evidence",
        ["rule_evaluation_id"],
        unique=False,
        postgresql_where=sa.text("rule_evaluation_id IS NOT NULL"),
    )
    op.create_table(
        "incident_impact",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("since", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["component.id"],
            name=op.f("fk_incident_impact_component_id_component"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incident.id"], name=op.f("fk_incident_impact_incident_id_incident")
        ),
        sa.PrimaryKeyConstraint("incident_id", "component_id", name=op.f("pk_incident_impact")),
    )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION iphi_reject_mutation()"
        )


def downgrade() -> None:
    for table in APPEND_ONLY:
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.drop_table("incident_impact")
    op.drop_index(
        "ix_incident_evidence_rule_evaluation_id",
        table_name="incident_evidence",
        postgresql_where=sa.text("rule_evaluation_id IS NOT NULL"),
    )
    op.drop_index(
        "ix_incident_evidence_metric_sample_id",
        table_name="incident_evidence",
        postgresql_where=sa.text("metric_sample_id IS NOT NULL"),
    )
    op.drop_index(
        "ix_incident_evidence_log_event_id",
        table_name="incident_evidence",
        postgresql_where=sa.text("log_event_id IS NOT NULL"),
    )
    op.drop_table("incident_evidence")
    op.drop_index("ix_incident_event_incident_id_occurred_at", table_name="incident_event")
    op.drop_table("incident_event")
    op.drop_index("ix_diagnostic_incident_id_created_at", table_name="diagnostic")
    op.drop_table("diagnostic")
    op.drop_index(
        "uq_incident_fingerprint_active",
        table_name="incident",
        postgresql_where=sa.text("status <> 'resolved'"),
    )
    op.drop_index("ix_incident_status_opened_at", table_name="incident")
    op.drop_index("ix_incident_opened_at_number", table_name="incident")
    op.drop_index("ix_incident_fingerprint_resolved_at", table_name="incident")
    op.drop_index("ix_incident_component_id_opened_at", table_name="incident")
    op.drop_table("incident")
