"""Stored health records as services and the API read them."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from app.health.domain.engine import Standing
from app.health.domain.evaluation import Evidence, Measurement
from app.health.domain.hysteresis import RuleProgress
from app.health.domain.rules import HealthRule
from app.health.domain.states import HealthState


@dataclass(frozen=True, slots=True)
class StoredRuleState:
    """A rule_state row as the API reads it."""

    component_id: uuid.UUID
    rule: HealthRule
    progress: RuleProgress
    measurement: Measurement
    evaluated_at: datetime
    last_evaluation_id: int
    state_evaluation_id: int


@dataclass(frozen=True, slots=True)
class StoredEvaluation:
    id: int
    rule: HealthRule
    component_id: uuid.UUID
    evaluated_at: datetime
    window_start: datetime
    measurement: Measurement
    state: HealthState


@dataclass(frozen=True, slots=True)
class EvaluationPosition:
    evaluated_at: datetime
    id: int


@dataclass(frozen=True, slots=True)
class EvaluationFilter:
    """Evaluations with `start <= evaluated_at < end`, newest first."""

    start: datetime
    end: datetime
    component_id: uuid.UUID | None
    rule_key: str | None
    state: HealthState | None
    before: EvaluationPosition | None
    limit: int


@dataclass(frozen=True, slots=True)
class StoredComponentHealth:
    component_id: uuid.UUID
    standing: Standing
    evaluated_at: datetime
    reason_evaluation_id: int | None
    impacted_by: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class StoredPlatformHealth:
    platform_id: uuid.UUID
    standing: Standing
    evaluated_at: datetime
    counts: Mapping[HealthState, int]
    priority: int | None
    rationale: str
    decided_by: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class RuleCondition:
    """Debounced state of a rule on a component, and what its latest measurement alone said."""

    state: HealthState
    raw_state: HealthState


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    """A rule evaluation stored by a health pass. `sets_state`: first evaluation of the rule on
    the component, or a state change; a rule's state changes at no other evaluation."""

    id: int
    component_id: uuid.UUID
    rule: HealthRule
    evaluated_at: datetime
    state: HealthState
    raw_state: HealthState
    sets_state: bool
    evidence: Evidence

    @property
    def condition(self) -> RuleCondition:
        return RuleCondition(self.state, self.raw_state)


@dataclass(frozen=True, slots=True)
class HealthPass:
    """What one evaluation pass stored, for the incident step of the same cycle.

    `before`: condition per (component, rule key) when the pass started; `outcomes`: stored
    evaluations in evaluated_at order; `rules`: the active rule versions; `history_start`: the
    instant the current history starts after (the latest reset).
    """

    history_start: datetime | None
    rules: tuple[HealthRule, ...]
    before: Mapping[tuple[uuid.UUID, str], RuleCondition]
    outcomes: tuple[EvaluationOutcome, ...]
