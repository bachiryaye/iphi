"""Ingestion: metric catalog, collection runs and cursors, metric samples and log events.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_cursor",
        sa.Column("connector_key", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("watermark", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('simulation', 'mqtt')", name=op.f("ck_collection_cursor_source")
        ),
        sa.PrimaryKeyConstraint("connector_key", name=op.f("pk_collection_cursor")),
    )
    op.create_table(
        "collection_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connector_key", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("log_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("rejections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("watermark", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "source IN ('simulation', 'mqtt')", name=op.f("ck_collection_run_source")
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'partial', 'failed')", name=op.f("ck_collection_run_status")
        ),
        sa.CheckConstraint(
            "finished_at >= started_at", name=op.f("ck_collection_run_finishes_after_start")
        ),
        sa.CheckConstraint(
            "sample_count >= 0 AND log_count >= 0 AND rejected_count >= 0 AND duplicate_count >= 0",
            name=op.f("ck_collection_run_counts_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_run")),
    )
    op.create_index(
        "ix_collection_run_connector_key_started_at",
        "collection_run",
        ["connector_key", "started_at"],
        unique=False,
    )
    op.create_index("ix_collection_run_started_at", "collection_run", ["started_at"], unique=False)
    op.create_table(
        "metric_definition",
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=False),
        sa.Column("min_value", sa.Double(), nullable=False),
        sa.Column("max_value", sa.Double(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "kind IN ('gauge', 'counter', 'ratio')", name=op.f("ck_metric_definition_kind")
        ),
        sa.CheckConstraint("min_value < max_value", name=op.f("ck_metric_definition_range")),
        sa.PrimaryKeyConstraint("metric_name", name=op.f("pk_metric_definition")),
    )
    op.create_table(
        "log_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("fingerprint", sa.String(length=16), nullable=False),
        sa.Column("dedup_key", sa.String(length=32), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("scenario_run_id", sa.Uuid(), nullable=True),
        sa.Column("collection_run_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "severity IN ('debug', 'info', 'warning', 'error', 'critical')",
            name=op.f("ck_log_event_severity"),
        ),
        sa.CheckConstraint("source IN ('simulation', 'mqtt')", name=op.f("ck_log_event_source")),
        sa.CheckConstraint(
            "char_length(message) BETWEEN 1 AND 2000", name=op.f("ck_log_event_message_length")
        ),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["collection_run.id"],
            name=op.f("fk_log_event_collection_run_id_collection_run"),
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["component.id"], name=op.f("fk_log_event_component_id_component")
        ),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"],
            ["scenario_run.id"],
            name=op.f("fk_log_event_scenario_run_id_scenario_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log_event")),
        sa.UniqueConstraint(
            "component_id",
            "observed_at",
            "source",
            "dedup_key",
            name=op.f("uq_log_event_component_id_observed_at_source_dedup_key"),
        ),
    )
    op.create_index(
        "ix_log_event_fingerprint_observed_at",
        "log_event",
        ["fingerprint", "observed_at"],
        unique=False,
    )
    op.create_index("ix_log_event_observed_at_id", "log_event", ["observed_at", "id"], unique=False)
    op.create_table(
        "metric_sample",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("quality", sa.String(length=16), nullable=False),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("scenario_run_id", sa.Uuid(), nullable=True),
        sa.Column("collection_run_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "quality IN ('good', 'uncertain', 'bad')", name=op.f("ck_metric_sample_quality")
        ),
        sa.CheckConstraint(
            "source IN ('simulation', 'mqtt')", name=op.f("ck_metric_sample_source")
        ),
        sa.CheckConstraint("value = value", name=op.f("ck_metric_sample_value_not_nan")),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["collection_run.id"],
            name=op.f("fk_metric_sample_collection_run_id_collection_run"),
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["component.id"], name=op.f("fk_metric_sample_component_id_component")
        ),
        sa.ForeignKeyConstraint(
            ["metric_name"],
            ["metric_definition.metric_name"],
            name=op.f("fk_metric_sample_metric_name_metric_definition"),
        ),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"],
            ["scenario_run.id"],
            name=op.f("fk_metric_sample_scenario_run_id_scenario_run"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_sample")),
        sa.UniqueConstraint(
            "component_id",
            "metric_name",
            "observed_at",
            "source",
            name=op.f("uq_metric_sample_component_id_metric_name_observed_at_source"),
        ),
    )
    op.create_index(
        "ix_metric_sample_observed_at_brin",
        "metric_sample",
        ["observed_at"],
        unique=False,
        postgresql_using="brin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_metric_sample_observed_at_brin", table_name="metric_sample", postgresql_using="brin"
    )
    op.drop_table("metric_sample")
    op.drop_index("ix_log_event_observed_at_id", table_name="log_event")
    op.drop_index("ix_log_event_fingerprint_observed_at", table_name="log_event")
    op.drop_table("log_event")
    op.drop_table("metric_definition")
    op.drop_index("ix_collection_run_started_at", table_name="collection_run")
    op.drop_index("ix_collection_run_connector_key_started_at", table_name="collection_run")
    op.drop_table("collection_run")
    op.drop_table("collection_cursor")
