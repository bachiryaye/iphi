import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.exceptions import IphiError
from app.core.observation import tick_time
from app.health.service import HealthHistory
from app.identity.domain import AuditAction, AuditContext, AuditEntry, AuditOutcome
from app.identity.service import AuditLog
from app.ingestion.service import ObservationHistory
from app.simulation.domain.catalog import CATALOG, SCENARIOS, ScenarioDefinition, ScenarioKey
from app.simulation.domain.clock import ClockMode, ClockState
from app.simulation.domain.errors import (
    BaselineRunPermanentError,
    ScenarioRunNotActiveError,
    ScenarioRunNotFoundError,
    ScenarioTargetBusyError,
    ScenarioTargetError,
    SimulationNotInitializedError,
)
from app.simulation.domain.generator import (
    MAX_TICKS_PER_BATCH,
    TickObservations,
    generate_range,
)
from app.simulation.domain.platform import SIMULATED_PLATFORM, SimulatedPlatform
from app.simulation.domain.runs import (
    RunStatus,
    ScenarioRun,
    StartRequest,
    baseline_plan,
    plan_run,
)
from app.simulation.domain.signals import OBSERVATION_SOURCE
from app.simulation.repository import ClockRepository, RunRepository
from app.topology.domain import PlatformTopology
from app.topology.service import TopologyService

SYSTEM_ACTOR = "system"

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ClockView:
    state: ClockState
    platform_time: datetime


@dataclass(frozen=True, slots=True)
class StartCommand:
    scenario: ScenarioKey
    target_key: str | None
    parameters: Mapping[str, float]
    duration_s: int | None


@dataclass(frozen=True, slots=True)
class RunPage:
    items: list[ScenarioRun]
    next_before: int | None


@dataclass(frozen=True, slots=True)
class ResetOutcome:
    clock: ClockView
    baseline: ScenarioRun
    stopped_runs: int


@dataclass(slots=True)
class _AuditDraft:
    platform_time: datetime | None = None
    target_type: str | None = None
    target_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def entry(
        self, context: AuditContext, action: AuditAction, outcome: AuditOutcome, at: datetime
    ) -> AuditEntry:
        return AuditEntry(
            context,
            action,
            outcome,
            at,
            self.platform_time,
            self.target_type,
            self.target_id,
            dict(self.details),
        )


@dataclass(frozen=True, slots=True)
class _Mutation:
    session: Session
    wall_now: datetime
    clock: ClockState
    audit: _AuditDraft

    @property
    def platform_now(self) -> datetime:
        return self.clock.platform_time(self.wall_now)


class SimulationService:
    """Scenario runs and the platform clock. Mutations are serialized by locking `sim_clock`."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        wall: Clock,
        topology: TopologyService,
        platform: SimulatedPlatform,
    ) -> None:
        self._session_factory = session_factory
        self._wall = wall
        self._topology_service = topology
        self._platform = platform
        self._loaded_topology: PlatformTopology | None = None

    def initialize(self, seed: int) -> None:
        """Idempotent bootstrap: creates the clock and the baseline run when missing."""
        wall_now = self._wall.now()
        with self._session_factory.begin() as session:
            clocks = ClockRepository(session)
            clocks.insert_if_missing(ClockState.initial(seed, wall_now), wall_now)
            clock = self._require_clock(clocks.get(for_update=True))
            runs = self._runs(session)
            if not any(r.scenario is ScenarioKey.BASELINE for r in runs.active()):
                started_at = clock.platform_time(wall_now)
                runs.add(baseline_plan(started_at, clock.seed, SYSTEM_ACTOR))
                log.info("simulation.initialized", seed=clock.seed, platform_time=started_at)

    def catalog(self) -> tuple[ScenarioDefinition, ...]:
        return CATALOG

    def clock(self) -> ClockView:
        with self._session_factory() as session:
            state = self._require_clock(ClockRepository(session).get(for_update=False))
        return ClockView(state, state.platform_time(self._wall.now()))

    def list_runs(self, status: RunStatus | None, before: int | None, limit: int) -> RunPage:
        with self._session_factory() as session:
            items = self._runs(session).page(status, before, limit + 1)
        if len(items) > limit:
            return RunPage(items[:limit], items[limit - 1].number)
        return RunPage(items, None)

    def start(self, command: StartCommand, context: AuditContext) -> ScenarioRun:
        definition = SCENARIOS[command.scenario]
        target_key = command.target_key or definition.default_target
        with self._mutation(context, AuditAction.SCENARIO_START) as mutation:
            mutation.audit.details.update(scenario=command.scenario.value, target=target_key)
            target = None if target_key is None else self._topology().component(target_key)
            if target_key is not None and target is None:
                raise ScenarioTargetError(f"Unknown component {target_key!r}.")
            request = StartRequest(definition, target, command.parameters, command.duration_s)
            plan = plan_run(
                request, mutation.platform_now, mutation.clock.seed, context.actor_label
            )
            runs = self._runs(mutation.session)
            self._complete_due(runs, mutation.platform_now)
            busy = next((r for r in runs.active() if r.target_key == target_key), None)
            if busy is not None:
                raise ScenarioTargetBusyError(
                    f"{target_key} already runs {busy.scenario} #{busy.number}; stop it first."
                )
            run = runs.add(plan)
            mutation.audit.target_type, mutation.audit.target_id = "scenario_run", str(run.id)
        log.info(
            "scenario.started",
            run_id=run.id,
            number=run.number,
            scenario=run.scenario,
            target=run.target_key,
            source=OBSERVATION_SOURCE,
        )
        return run

    def stop(self, run_id: uuid.UUID, context: AuditContext) -> ScenarioRun:
        with self._mutation(context, AuditAction.SCENARIO_STOP) as mutation:
            mutation.audit.target_type, mutation.audit.target_id = "scenario_run", str(run_id)
            runs = self._runs(mutation.session)
            self._complete_due(runs, mutation.platform_now)
            run = runs.get(run_id, for_update=True)
            if run is None:
                raise ScenarioRunNotFoundError(f"No scenario run {run_id}.")
            if run.scenario is ScenarioKey.BASELINE:
                raise BaselineRunPermanentError("The baseline run cannot be stopped; use reset.")
            if run.status is not RunStatus.ACTIVE:
                raise ScenarioRunNotActiveError(f"Scenario run #{run.number} is {run.status}.")
            stopped = runs.finish(run.id, RunStatus.STOPPED, mutation.platform_now)
        log.info(
            "scenario.stopped", run_id=run_id, number=stopped.number, source=OBSERVATION_SOURCE
        )
        return stopped

    def reset(self, seed: int, context: AuditContext) -> ResetOutcome:
        """Stops every run, restarts the clock in realtime with `seed` and a fresh baseline, and
        purges the simulated observations with the health state derived from them."""
        with self._mutation(context, AuditAction.SIMULATION_RESET) as mutation:
            mutation.audit.details["seed"] = seed
            clock = mutation.clock.reset(seed, mutation.wall_now)
            # A clock behind wall time jumps forward at reset. Old runs end exactly where the
            # new baseline starts, so no tick is left without a baseline, and runs due in the
            # jump complete at their planned end rather than being stopped after it.
            started_at = clock.platform_time(mutation.wall_now)
            runs = self._runs(mutation.session)
            self._complete_due(runs, started_at)
            active = runs.active()
            for run in active:
                runs.finish(run.id, RunStatus.STOPPED, started_at)
            ClockRepository(mutation.session).save(clock, mutation.wall_now)
            baseline = runs.add(baseline_plan(started_at, seed, context.actor_label))
            purged = ObservationHistory(mutation.session).purge_source(OBSERVATION_SOURCE)
            mutation.audit.details["purged_observations"] = purged
            # V1 platforms are simulated only: every health state derives from what was purged.
            mutation.audit.details["purged_evaluations"] = HealthHistory(mutation.session).clear()
        log.info(
            "simulation.reset",
            seed=seed,
            stopped_runs=len(active),
            purged_observations=purged,
            platform_time=started_at,
        )
        return ResetOutcome(ClockView(clock, started_at), baseline, len(active))

    def set_clock_mode(self, mode: ClockMode, speed: float, context: AuditContext) -> ClockView:
        with self._mutation(context, AuditAction.CLOCK_UPDATE) as mutation:
            mutation.audit.details.update(operation="set_mode", mode=mode.value, speed=speed)
            clock = mutation.clock.switched(mode, speed, mutation.wall_now)
            ClockRepository(mutation.session).save(clock, mutation.wall_now)
        log.info("clock.mode_changed", mode=mode, speed=speed)
        return ClockView(clock, clock.platform_time(mutation.wall_now))

    def advance_clock(self, seconds: int, context: AuditContext) -> ClockView:
        with self._mutation(context, AuditAction.CLOCK_UPDATE) as mutation:
            mutation.audit.details.update(operation="advance", seconds=seconds)
            clock = mutation.clock.advanced(seconds, mutation.wall_now)
            ClockRepository(mutation.session).save(clock, mutation.wall_now)
            platform_now = clock.platform_time(mutation.wall_now)
            self._complete_due(self._runs(mutation.session), platform_now)
        log.info("clock.advanced", seconds=seconds, platform_time=platform_now)
        return ClockView(clock, platform_now)

    def begin_cycle(self, session: Session) -> datetime:
        """Worker step 1, in the cycle's unit of work: platform time, with due runs completed.

        The shared lock on sim_clock lasts until the cycle commits, so a reset or a scenario
        change waits for the cycle in progress and the next cycle sees it whole: a reset can
        never purge observations that a cycle generated from the runs it stopped.
        """
        clock = self._require_clock(ClockRepository(session).get_shared())
        now = clock.platform_time(self._wall.now())
        self._complete_due(self._runs(session), now)
        return now

    def coverage_start(self) -> datetime:
        """Start of the active baseline: no earlier sample slot belongs to the current history."""
        with self._session_factory() as session:
            baseline = next(
                (r for r in self._runs(session).active() if r.scenario is ScenarioKey.BASELINE),
                None,
            )
        if baseline is None:
            raise SimulationNotInitializedError("No active baseline run; reset the simulation.")
        return baseline.started_at

    def observations(self, first_tick: int, last_tick: int) -> list[TickObservations]:
        """Simulated observations for ticks `first_tick`..`last_tick`, from persisted runs only."""
        if not 0 <= last_tick - first_tick < MAX_TICKS_PER_BATCH:
            raise ValueError(f"a batch spans 1 to {MAX_TICKS_PER_BATCH} ticks")
        with self._session_factory() as session:
            runs = self._runs(session).overlapping(tick_time(first_tick), tick_time(last_tick))
        return generate_range(self._platform, runs, first_tick, last_tick)

    @contextmanager
    def _mutation(self, context: AuditContext, action: AuditAction) -> Iterator[_Mutation]:
        """Serialized, audited unit of work; a refused action is audited as `failed` (X-14)."""
        wall_now = self._wall.now()
        draft = _AuditDraft()
        try:
            with self._session_factory.begin() as session:
                clock = self._require_clock(ClockRepository(session).get(for_update=True))
                draft.platform_time = clock.platform_time(wall_now)
                yield _Mutation(session, wall_now, clock, draft)
                AuditLog(session).record(
                    draft.entry(context, action, AuditOutcome.ALLOWED, wall_now)
                )
        except IphiError as exc:
            draft.details["error_code"] = exc.code
            with self._session_factory.begin() as session:
                AuditLog(session).record(
                    draft.entry(context, action, AuditOutcome.FAILED, wall_now)
                )
            raise

    @staticmethod
    def _complete_due(runs: RunRepository, now: datetime) -> list[ScenarioRun]:
        completed = runs.complete_due(now)
        for run in completed:
            log.info("scenario.completed", run_id=run.id, number=run.number)
        return completed

    def _runs(self, session: Session) -> RunRepository:
        return RunRepository(session, self._topology())

    def _topology(self) -> PlatformTopology:
        # Components only change at seed time, in the bootstrap process that runs first.
        if self._loaded_topology is not None:
            return self._loaded_topology
        topology = self._topology_service.platform(self._platform.key)
        if topology is None:
            raise SimulationNotInitializedError(
                f"Platform {self._platform.key} is not seeded; run the bootstrap."
            )
        self._loaded_topology = topology
        return topology

    @staticmethod
    def _require_clock(state: ClockState | None) -> ClockState:
        if state is None:
            raise SimulationNotInitializedError(
                "The platform clock is not seeded; run the bootstrap."
            )
        return state


def build_simulation(session_factory: sessionmaker[Session], wall: Clock) -> SimulationService:
    """The simulation service of the seeded platform, as every process wires it."""
    return SimulationService(
        session_factory, wall, TopologyService(session_factory), SIMULATED_PLATFORM
    )
