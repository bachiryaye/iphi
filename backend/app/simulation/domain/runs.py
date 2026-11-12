import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from app.simulation.domain.catalog import ScenarioDefinition, ScenarioKey, ScenarioKind
from app.simulation.domain.errors import (
    ScenarioNotStartableError,
    ScenarioParameterError,
    ScenarioTargetError,
)
from app.topology.domain import Component

MIN_DURATION_S = 10
MAX_DURATION_S = 7 * 24 * 3600


class RunStatus(StrEnum):
    ACTIVE = "active"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class RunPlan:
    """A validated request to start a scenario, before it is persisted."""

    scenario: ScenarioKey
    target: Component | None
    seed: int
    parameters: Mapping[str, float]
    started_at: datetime
    ends_at: datetime | None
    started_by: str


@dataclass(frozen=True, slots=True)
class ScenarioRun:
    id: uuid.UUID
    number: int
    scenario: ScenarioKey
    target_key: str | None
    seed: int
    parameters: Mapping[str, float]
    started_at: datetime
    ends_at: datetime | None
    stopped_at: datetime | None
    status: RunStatus
    started_by: str

    @property
    def end(self) -> datetime | None:
        # Runs are completed at their planned end, never stopped after it: stopped_at <= ends_at.
        return self.stopped_at or self.ends_at

    @classmethod
    def from_plan(cls, plan: RunPlan, run_id: uuid.UUID, number: int) -> ScenarioRun:
        return cls(
            id=run_id,
            number=number,
            scenario=plan.scenario,
            target_key=None if plan.target is None else plan.target.key,
            seed=plan.seed,
            parameters=plan.parameters,
            started_at=plan.started_at,
            ends_at=plan.ends_at,
            stopped_at=None,
            status=RunStatus.ACTIVE,
            started_by=plan.started_by,
        )

    def covers(self, at: datetime) -> bool:
        """Whether the run shapes observations at `at`; status is bookkeeping, time decides."""
        return self.started_at <= at and (self.end is None or at < self.end)


@dataclass(frozen=True, slots=True)
class StartRequest:
    definition: ScenarioDefinition
    target: Component | None
    parameters: Mapping[str, float]
    duration_s: int | None


def plan_run(request: StartRequest, started_at: datetime, seed: int, started_by: str) -> RunPlan:
    definition, target = request.definition, request.target
    if definition.kind is ScenarioKind.BASELINE:
        raise ScenarioNotStartableError("The baseline runs permanently; use reset to restart it.")
    if target is None:
        raise ScenarioTargetError(f"Scenario {definition.key} needs a target component.")
    if target.type not in definition.eligible_types:
        eligible = ", ".join(sorted(definition.eligible_types))
        raise ScenarioTargetError(
            f"Scenario {definition.key} applies to {eligible} components, not {target.type}."
        )
    parameters = _resolve_parameters(definition, request.parameters)
    duration_s = request.duration_s
    if duration_s is not None and not MIN_DURATION_S <= duration_s <= MAX_DURATION_S:
        raise ScenarioParameterError(
            f"duration_s must be between {MIN_DURATION_S} and {MAX_DURATION_S}."
        )
    ends_at = None if duration_s is None else started_at + timedelta(seconds=duration_s)
    return RunPlan(definition.key, target, seed, parameters, started_at, ends_at, started_by)


def _resolve_parameters(
    definition: ScenarioDefinition, given: Mapping[str, float]
) -> Mapping[str, float]:
    specs = {p.name: p for p in definition.parameters}
    unknown = sorted(given.keys() - specs.keys())
    if unknown:
        raise ScenarioParameterError(
            f"Unknown parameter(s) for {definition.key}: {', '.join(unknown)}."
        )
    resolved: dict[str, float] = {}
    for name, spec in specs.items():
        value = float(given.get(name, spec.default))
        if not spec.minimum <= value <= spec.maximum:
            raise ScenarioParameterError(
                f"{name} must be between {spec.minimum:g} and {spec.maximum:g} {spec.unit}."
            )
        resolved[name] = value
    return MappingProxyType(resolved)


def baseline_plan(started_at: datetime, seed: int, started_by: str) -> RunPlan:
    return RunPlan(
        ScenarioKey.BASELINE, None, seed, MappingProxyType({}), started_at, None, started_by
    )
