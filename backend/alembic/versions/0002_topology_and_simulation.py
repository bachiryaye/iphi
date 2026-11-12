"""Topology (component, dependency) and simulation state (sim_clock, scenario_run).

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sim_clock",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("speed", sa.Float(), nullable=False),
        sa.Column("anchor_platform_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("anchor_wall_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(mode = 'accelerated' AND speed > 1 AND speed <= 60) "
            "OR (mode <> 'accelerated' AND speed = 1)",
            name=op.f("ck_sim_clock_speed"),
        ),
        sa.CheckConstraint(
            "mode IN ('realtime', 'accelerated', 'manual')", name=op.f("ck_sim_clock_mode")
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_sim_clock_single_row")),
        sa.CheckConstraint("seed BETWEEN 0 AND 2147483647", name=op.f("ck_sim_clock_seed")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sim_clock")),
    )
    op.create_table(
        "component",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("criticality", sa.String(length=8), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "criticality IN ('high', 'medium', 'low')", name=op.f("ck_component_criticality")
        ),
        sa.CheckConstraint(
            "type IN ('source', 'gateway', 'collector', 'historian', 'database', 'api', "
            "'analytics')",
            name=op.f("ck_component_type"),
        ),
        sa.ForeignKeyConstraint(
            ["platform_id"], ["platform.id"], name=op.f("fk_component_platform_id_platform")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_component")),
        sa.UniqueConstraint("platform_id", "key", name=op.f("uq_component_platform_id_key")),
    )
    op.create_table(
        "dependency",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform_id", sa.Uuid(), nullable=False),
        sa.Column("dependent_component_id", sa.Uuid(), nullable=False),
        sa.Column("dependency_component_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.CheckConstraint("kind IN ('data_flow', 'runtime')", name=op.f("ck_dependency_kind")),
        sa.CheckConstraint(
            "dependent_component_id <> dependency_component_id", name=op.f("ck_dependency_not_self")
        ),
        sa.ForeignKeyConstraint(
            ["dependency_component_id"],
            ["component.id"],
            name=op.f("fk_dependency_dependency_component_id_component"),
        ),
        sa.ForeignKeyConstraint(
            ["dependent_component_id"],
            ["component.id"],
            name=op.f("fk_dependency_dependent_component_id_component"),
        ),
        sa.ForeignKeyConstraint(
            ["platform_id"], ["platform.id"], name=op.f("fk_dependency_platform_id_platform")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dependency")),
        sa.UniqueConstraint(
            "dependent_component_id",
            "dependency_component_id",
            name=op.f("uq_dependency_dependent_component_id_dependency_component_id"),
        ),
    )
    op.create_index(
        "ix_dependency_dependency_component_id",
        "dependency",
        ["dependency_component_id"],
        unique=False,
    )
    op.create_table(
        "scenario_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("platform_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_key", sa.String(length=32), nullable=False),
        sa.Column("target_component_id", sa.Uuid(), nullable=True),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_by", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scenario_key = 'baseline') = (target_component_id IS NULL)",
            name=op.f("ck_scenario_run_target"),
        ),
        sa.CheckConstraint(
            "(status = 'active') = (stopped_at IS NULL)", name=op.f("ck_scenario_run_stopped_at")
        ),
        sa.CheckConstraint(
            "scenario_key IN ('baseline', 'collector_down', 'latency_rise', 'stale_data', "
            "'intermittent_loss', 'error_burst', 'resource_pressure', 'backlog_growth', "
            "'telemetry_blackout')",
            name=op.f("ck_scenario_run_scenario_key"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'stopped', 'completed')", name=op.f("ck_scenario_run_status")
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > started_at", name=op.f("ck_scenario_run_ends_after_start")
        ),
        sa.CheckConstraint(
            "stopped_at IS NULL OR stopped_at >= started_at",
            name=op.f("ck_scenario_run_stops_after_start"),
        ),
        sa.ForeignKeyConstraint(
            ["platform_id"], ["platform.id"], name=op.f("fk_scenario_run_platform_id_platform")
        ),
        sa.ForeignKeyConstraint(
            ["target_component_id"],
            ["component.id"],
            name=op.f("fk_scenario_run_target_component_id_component"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_run")),
        sa.UniqueConstraint("number", name=op.f("uq_scenario_run_number")),
    )
    op.create_index(
        "ix_scenario_run_platform_id_started_at",
        "scenario_run",
        ["platform_id", "started_at"],
        unique=False,
    )
    op.create_index("ix_scenario_run_status", "scenario_run", ["status"], unique=False)
    op.create_index(
        "uq_scenario_run_active_baseline",
        "scenario_run",
        ["platform_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND scenario_key = 'baseline'"),
    )
    op.create_index(
        "uq_scenario_run_active_target",
        "scenario_run",
        ["target_component_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_scenario_run_active_target",
        table_name="scenario_run",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        "uq_scenario_run_active_baseline",
        table_name="scenario_run",
        postgresql_where=sa.text("status = 'active' AND scenario_key = 'baseline'"),
    )
    op.drop_index("ix_scenario_run_status", table_name="scenario_run")
    op.drop_index("ix_scenario_run_platform_id_started_at", table_name="scenario_run")
    op.drop_table("scenario_run")
    op.drop_index("ix_dependency_dependency_component_id", table_name="dependency")
    op.drop_table("dependency")
    op.drop_table("component")
    op.drop_table("sim_clock")
