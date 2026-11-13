"""Drives the production worker cycle on a manual platform clock and reads health results."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import seed
from app.health.domain.states import HealthState
from app.identity.domain import AuditContext
from app.simulation.domain.catalog import ScenarioKey
from app.simulation.domain.clock import ClockMode
from app.simulation.domain.runs import ScenarioRun
from app.simulation.service import SimulationService, StartCommand
from app.worker import Worker
from tests.fakes import FixedClock, cycling_worker
from tests.simulation_runs import GOLDEN_SEED

CONTEXT = AuditContext("dev-local", "corr-health-test")
STEP_S = 30
# Long enough for every rule to leave its initial Unknown (clear_after 3 slots): the slot the
# baseline starts at is not evaluated (ADR 0017), the first pass evaluates only its newest slot.
WARMUP_S = 60


@dataclass
class Platform:
    """A seeded platform on a manual clock, cycled by the production worker steps."""

    simulation: SimulationService
    worker: Worker
    engine: Engine

    def advance(self, seconds: int, step: int = STEP_S) -> None:
        for _ in range(seconds // step):
            self.simulation.advance_clock(step, CONTEXT)
            self.worker.run_cycle(0)

    def start(self, scenario: ScenarioKey, target: str | None = None) -> ScenarioRun:
        return self.simulation.start(StartCommand(scenario, target, {}, None), CONTEXT)

    def stop(self, run: ScenarioRun) -> None:
        self.simulation.stop(run.id, CONTEXT)

    def rule_states(self, component: str, rule: str) -> list[HealthState]:
        """Successive states of a rule on a component; every change is a stored evaluation."""
        rows = self.rows(
            "SELECT e.state FROM rule_evaluation e JOIN health_rule r ON r.id = e.rule_id "
            "JOIN component c ON c.id = e.component_id WHERE c.key = :component "
            "AND r.key = :rule ORDER BY e.evaluated_at",
            component=component,
            rule=rule,
        )
        states: list[HealthState] = []
        for (state,) in rows:
            if not states or states[-1] != state:
                states.append(HealthState(state))
        return states

    def component_state(self, component: str) -> HealthState:
        (row,) = self.rows(
            "SELECT h.state FROM component_health h JOIN component c ON c.id = h.component_id "
            "WHERE c.key = :component",
            component=component,
        )
        return HealthState(row[0])

    def component_states(self) -> dict[str, HealthState]:
        rows = self.rows(
            "SELECT c.key, h.state FROM component_health h "
            "JOIN component c ON c.id = h.component_id"
        )
        return {key: HealthState(state) for key, state in rows}

    def impacted(self, component: str) -> set[str]:
        rows = self.rows(
            "SELECT u.key FROM component_health h JOIN component c ON c.id = h.component_id "
            "JOIN component u ON u.id = ANY(h.impacted_by) WHERE c.key = :component",
            component=component,
        )
        return {r[0] for r in rows}

    def platform_state(self) -> tuple[HealthState, int | None]:
        (row,) = self.rows("SELECT state, priority FROM platform_health")
        return HealthState(row[0]), row[1]

    def incidents(self) -> list[Any]:
        """(component, failure class, status, severity, occurrences, resolution), oldest first."""
        return self.rows(
            "SELECT c.key, i.failure_class, i.status, i.severity, i.occurrence_count, "
            "i.resolution FROM incident i JOIN component c ON c.id = i.component_id "
            "ORDER BY i.number"
        )

    def active_incidents(self) -> set[tuple[str, str]]:
        return {(r[0], r[1]) for r in self.incidents() if r[2] != "resolved"}

    def events(self, component: str, failure_class: str) -> list[str]:
        rows = self.rows(
            "SELECT e.event_type FROM incident_event e JOIN incident i ON i.id = e.incident_id "
            "JOIN component c ON c.id = i.component_id WHERE c.key = :component "
            "AND i.failure_class = :failure_class ORDER BY e.occurred_at, e.id",
            component=component,
            failure_class=failure_class,
        )
        return [r[0] for r in rows]

    def rows(self, sql: str, **params: Any) -> list[Any]:
        """Rows of a read-only test query."""
        with self.engine.connect() as connection:
            return list(connection.execute(text(sql), params))


def manual_platform(
    session_factory: sessionmaker[Session], engine: Engine, wall: FixedClock
) -> Platform:
    """Seeded, on a manual clock, warmed up until every rule has a known state."""
    simulation = seed(session_factory, wall, GOLDEN_SEED)
    simulation.set_clock_mode(ClockMode.MANUAL, 1.0, CONTEXT)
    platform = Platform(simulation, cycling_worker(session_factory, wall), engine)
    platform.worker.run_cycle(0)
    platform.advance(WARMUP_S)
    return platform
