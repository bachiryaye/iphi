import uuid
from datetime import datetime
from types import MappingProxyType
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Float,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, check_in
from app.core.settings import MAX_SEED
from app.simulation.domain.catalog import ScenarioKey
from app.simulation.domain.clock import MAX_ACCELERATION, ClockMode, ClockState
from app.simulation.domain.runs import RunPlan, RunStatus, ScenarioRun
from app.topology.domain import PlatformTopology

CLOCK_ROW_ID = 1
ACTIVE_TARGET_INDEX = "uq_scenario_run_active_target"
ACTIVE_BASELINE_INDEX = "uq_scenario_run_active_baseline"
# Runs overlapping a generation window; far above what a demo session creates.
MAX_OVERLAPPING_RUNS = 500


class SimClockRecord(Base):
    __tablename__ = "sim_clock"
    __table_args__ = (
        CheckConstraint(f"id = {CLOCK_ROW_ID}", name="single_row"),
        CheckConstraint(check_in("mode", ClockMode), name="mode"),
        CheckConstraint(
            f"(mode = 'accelerated' AND speed > 1 AND speed <= {MAX_ACCELERATION:g}) "
            "OR (mode <> 'accelerated' AND speed = 1)",
            name="speed",
        ),
        CheckConstraint(f"seed BETWEEN 0 AND {MAX_SEED}", name="seed"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    mode: Mapped[str] = mapped_column(String(16))
    speed: Mapped[float] = mapped_column(Float)
    anchor_platform_time: Mapped[datetime]
    anchor_wall_time: Mapped[datetime]
    seed: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime]


class ScenarioRunRecord(Base):
    __tablename__ = "scenario_run"
    __table_args__ = (
        CheckConstraint(check_in("scenario_key", ScenarioKey), name="scenario_key"),
        CheckConstraint(check_in("status", RunStatus), name="status"),
        CheckConstraint(
            "(scenario_key = 'baseline') = (target_component_id IS NULL)", name="target"
        ),
        CheckConstraint("(status = 'active') = (stopped_at IS NULL)", name="stopped_at"),
        CheckConstraint("ends_at IS NULL OR ends_at > started_at", name="ends_after_start"),
        CheckConstraint("stopped_at IS NULL OR stopped_at >= started_at", name="stops_after_start"),
        Index("ix_scenario_run_status", "status"),
        Index("ix_scenario_run_platform_id_started_at", "platform_id", "started_at"),
        # One fault per component at a time, one baseline per platform: enforced by the database.
        Index(
            ACTIVE_TARGET_INDEX,
            "target_component_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            ACTIVE_BASELINE_INDEX,
            "platform_id",
            unique=True,
            postgresql_where=text("status = 'active' AND scenario_key = 'baseline'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.id"))
    scenario_key: Mapped[str] = mapped_column(String(32))
    target_component_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("component.id"))
    seed: Mapped[int] = mapped_column(BigInteger)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    started_at: Mapped[datetime]
    ends_at: Mapped[datetime | None]
    stopped_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(16))
    started_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ClockRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, for_update: bool) -> ClockState | None:
        statement = select(SimClockRecord).where(SimClockRecord.id == CLOCK_ROW_ID)
        if for_update:
            statement = statement.with_for_update()
        record = self._session.scalars(statement).one_or_none()
        if record is None:
            return None
        return ClockState(
            mode=ClockMode(record.mode),
            speed=record.speed,
            anchor_platform_time=record.anchor_platform_time,
            anchor_wall_time=record.anchor_wall_time,
            seed=record.seed,
        )

    def insert_if_missing(self, state: ClockState, updated_at: datetime) -> None:
        values = self._values(state, updated_at)
        statement = insert(SimClockRecord).values(id=CLOCK_ROW_ID, **values)
        self._session.execute(statement.on_conflict_do_nothing(index_elements=["id"]))

    def save(self, state: ClockState, updated_at: datetime) -> None:
        values = self._values(state, updated_at)
        statement = insert(SimClockRecord).values(id=CLOCK_ROW_ID, **values)
        self._session.execute(statement.on_conflict_do_update(index_elements=["id"], set_=values))

    @staticmethod
    def _values(state: ClockState, updated_at: datetime) -> dict[str, Any]:
        return {
            "mode": state.mode.value,
            "speed": state.speed,
            "anchor_platform_time": state.anchor_platform_time,
            "anchor_wall_time": state.anchor_wall_time,
            "seed": state.seed,
            "updated_at": updated_at,
        }


class RunRepository:
    """Scenario runs of one platform; target components are exchanged by key."""

    def __init__(self, session: Session, topology: PlatformTopology) -> None:
        self._session = session
        self._platform_id = topology.platform_id
        self._keys = topology.keys_by_id()

    def add(self, plan: RunPlan) -> ScenarioRun:
        record = ScenarioRunRecord(
            platform_id=self._platform_id,
            scenario_key=plan.scenario.value,
            target_component_id=None if plan.target is None else plan.target.id,
            seed=plan.seed,
            parameters=dict(plan.parameters),
            started_at=plan.started_at,
            ends_at=plan.ends_at,
            stopped_at=None,
            status=RunStatus.ACTIVE.value,
            started_by=plan.started_by,
        )
        self._session.add(record)
        self._session.flush()
        return self._to_run(record)

    def get(self, run_id: uuid.UUID, *, for_update: bool) -> ScenarioRun | None:
        statement = select(ScenarioRunRecord).where(
            ScenarioRunRecord.id == run_id, ScenarioRunRecord.platform_id == self._platform_id
        )
        if for_update:
            statement = statement.with_for_update()
        record = self._session.scalars(statement).one_or_none()
        return None if record is None else self._to_run(record)

    def page(self, status: RunStatus | None, before: int | None, limit: int) -> list[ScenarioRun]:
        """Newest first by run number (keyset pagination)."""
        statement = select(ScenarioRunRecord).where(
            ScenarioRunRecord.platform_id == self._platform_id
        )
        if status is not None:
            statement = statement.where(ScenarioRunRecord.status == status.value)
        if before is not None:
            statement = statement.where(ScenarioRunRecord.number < before)
        statement = statement.order_by(ScenarioRunRecord.number.desc()).limit(limit)
        return [self._to_run(r) for r in self._session.scalars(statement)]

    def active(self) -> list[ScenarioRun]:
        statement = (
            select(ScenarioRunRecord)
            .where(
                ScenarioRunRecord.platform_id == self._platform_id,
                ScenarioRunRecord.status == RunStatus.ACTIVE.value,
            )
            .order_by(ScenarioRunRecord.number)
        )
        return [self._to_run(r) for r in self._session.scalars(statement)]

    def overlapping(self, start: datetime, end: datetime) -> list[ScenarioRun]:
        """Runs whose [started_at, end) interval intersects [start, end]."""
        run_end = func.coalesce(ScenarioRunRecord.stopped_at, ScenarioRunRecord.ends_at)
        statement = (
            select(ScenarioRunRecord)
            .where(
                ScenarioRunRecord.platform_id == self._platform_id,
                ScenarioRunRecord.started_at <= end,
                or_(run_end.is_(None), run_end > start),
            )
            .order_by(ScenarioRunRecord.number)
            .limit(MAX_OVERLAPPING_RUNS + 1)
        )
        records = list(self._session.scalars(statement))
        if len(records) > MAX_OVERLAPPING_RUNS:
            # Truncating would silently drop fault runs from the generated observations.
            raise RuntimeError(f"more than {MAX_OVERLAPPING_RUNS} runs overlap {start}..{end}")
        return [self._to_run(r) for r in records]

    def finish(self, run_id: uuid.UUID, status: RunStatus, stopped_at: datetime) -> ScenarioRun:
        statement = (
            update(ScenarioRunRecord)
            .where(ScenarioRunRecord.id == run_id)
            .values(status=status.value, stopped_at=stopped_at)
            .returning(ScenarioRunRecord)
        )
        return self._to_run(self._session.scalars(statement).one())

    def complete_due(self, now: datetime) -> list[ScenarioRun]:
        """Active runs whose planned end is at or before `now` become completed at that end."""
        statement = (
            update(ScenarioRunRecord)
            .where(
                ScenarioRunRecord.platform_id == self._platform_id,
                ScenarioRunRecord.status == RunStatus.ACTIVE.value,
                ScenarioRunRecord.ends_at <= now,
            )
            .values(status=RunStatus.COMPLETED.value, stopped_at=ScenarioRunRecord.ends_at)
            .returning(ScenarioRunRecord)
        )
        return [self._to_run(r) for r in self._session.scalars(statement)]

    def _to_run(self, record: ScenarioRunRecord) -> ScenarioRun:
        target = record.target_component_id
        return ScenarioRun(
            id=record.id,
            number=record.number,
            scenario=ScenarioKey(record.scenario_key),
            target_key=None if target is None else self._keys[target],
            seed=record.seed,
            parameters=MappingProxyType({k: float(v) for k, v in record.parameters.items()}),
            started_at=record.started_at,
            ends_at=record.ends_at,
            stopped_at=record.stopped_at,
            status=RunStatus(record.status),
            started_by=record.started_by,
        )
