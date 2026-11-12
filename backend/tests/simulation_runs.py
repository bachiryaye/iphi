"""Builders of scenario runs for generator tests, mirroring what the service persists."""

import uuid
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from app.simulation.domain.catalog import SCENARIOS, ScenarioKey
from app.simulation.domain.clock import tick_of
from app.simulation.domain.runs import RunStatus, ScenarioRun

GOLDEN_START = datetime(2026, 1, 1, tzinfo=UTC)
GOLDEN_SEED = 42
GOLDEN_TICKS = 120
FIRST_TICK = tick_of(GOLDEN_START)
# Seed 42, baseline + collector_down on collector-01 from GOLDEN_START, 120 ticks. Changes only
# when the generator, the platform profile or the catalog changes on purpose.
GOLDEN_COLLECTOR_DOWN = "df67ef15df8ffe50249e2e5d18982eeefc027c3fff9ae90584c7faf134152cbc"


def make_run(
    scenario: ScenarioKey,
    target: str | None = None,
    *,
    seed: int = GOLDEN_SEED,
    stopped_after_s: float | None = None,
    parameters: dict[str, float] | None = None,
) -> ScenarioRun:
    stopped_at = (
        None if stopped_after_s is None else GOLDEN_START + timedelta(seconds=stopped_after_s)
    )
    return ScenarioRun(
        id=uuid.uuid4(),
        number=1,
        scenario=scenario,
        target_key=target,
        seed=seed,
        parameters=MappingProxyType(_resolved(scenario, parameters or {})),
        started_at=GOLDEN_START,
        ends_at=None,
        stopped_at=stopped_at,
        status=RunStatus.ACTIVE if stopped_at is None else RunStatus.STOPPED,
        started_by="test",
    )


def baseline(seed: int = GOLDEN_SEED) -> ScenarioRun:
    return make_run(ScenarioKey.BASELINE, seed=seed)


def _resolved(scenario: ScenarioKey, given: dict[str, float]) -> dict[str, float]:
    """Defaults filled in, as plan_run persists them."""
    return {p.name: given.get(p.name, p.default) for p in SCENARIOS[scenario].parameters}
