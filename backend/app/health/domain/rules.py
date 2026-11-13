"""Health rule definitions (architecture §03.1, §05.3; ADR 0004).

A definition is the full content of one immutable rule version: changing any field, a
threshold or the rationale alike, makes a new version (D-08). Invariants are checked here so
a rule without hysteresis or with inconsistent thresholds never reaches the engine (D-09).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.observation import SAMPLE_INTERVAL_S
from app.topology.domain import Component, ComponentType

RULE_KEY_PATTERN = r"^R-[A-Z]{2,8}-[0-9]{3}$"
MAX_WINDOW_SECONDS = 3600
MAX_CONSECUTIVE_EVALUATIONS = 100
MAX_TEXT_CHARS = 500


class RuleDefinitionError(ValueError):
    pass


class RuleType(StrEnum):
    THRESHOLD = "threshold"
    FRESHNESS = "freshness"
    ABSENCE = "absence"
    AVAILABILITY_RATIO = "availability_ratio"


class FailureClass(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    FRESHNESS = "freshness"
    ERRORS = "errors"
    RESOURCES = "resources"
    BACKLOG = "backlog"
    CONNECTIVITY = "connectivity"
    TELEMETRY_LOSS = "telemetry_loss"


class Aggregation(StrEnum):
    LAST = "last"
    AVG = "avg"
    MAX = "max"
    P95 = "p95"
    SUM = "sum"
    RATIO = "ratio"


class Operator(StrEnum):
    GT = "gt"
    GE = "ge"
    LT = "lt"

    @property
    def upward(self) -> bool:
        """True when higher values are worse."""
        return self is not Operator.LT

    @property
    def symbol(self) -> str:
        return {Operator.GT: ">", Operator.GE: "≥", Operator.LT: "<"}[self]

    def breaches(self, value: float, threshold: float) -> bool:
        if self is Operator.GT:
            return value > threshold
        if self is Operator.GE:
            return value >= threshold
        return value < threshold


@dataclass(frozen=True, slots=True)
class Level:
    """Raise when the operator holds at `threshold`; clear once it no longer holds at `clear`."""

    threshold: float
    clear: float

    @property
    def has_deadband(self) -> bool:
        return self.threshold != self.clear


@dataclass(frozen=True, slots=True)
class Measure:
    """What a measured rule computes over its window and the levels it compares against."""

    metric_name: str
    aggregation: Aggregation
    operator: Operator
    warning: Level | None
    critical: Level | None

    def __post_init__(self) -> None:
        if not self.levels:
            raise RuleDefinitionError("a measured rule needs a warning or a critical level")
        upward = self.operator.upward
        for level in self.levels:
            if (level.clear > level.threshold) if upward else (level.clear < level.threshold):
                raise RuleDefinitionError("a clear threshold lies on the breaching side")
        if self.warning is not None and self.critical is not None:
            sign = 1 if upward else -1
            if sign * (self.critical.threshold - self.warning.threshold) <= 0:
                raise RuleDefinitionError("the critical threshold must be beyond the warning one")
            if sign * (self.critical.clear - self.warning.clear) < 0:
                raise RuleDefinitionError("the critical clear must not be inside the warning clear")

    @property
    def levels(self) -> tuple[Level, ...]:
        return tuple(lvl for lvl in (self.warning, self.critical) if lvl is not None)

    @property
    def lowest(self) -> Level:
        """The first level a degrading value breaches."""
        return self.levels[0]


@dataclass(frozen=True, slots=True)
class TargetSelector:
    """Components a rule applies to: listed types or keys; both empty means every component."""

    component_types: frozenset[ComponentType] = frozenset()
    component_keys: frozenset[str] = frozenset()

    def applies_to(self, component: Component) -> bool:
        if not self.component_types and not self.component_keys:
            return True
        return component.type in self.component_types or component.key in self.component_keys


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    """`measure` is None exactly for absence rules, which watch any observation (ADR 0003)."""

    rule_type: RuleType
    failure_class: FailureClass
    targets: TargetSelector
    measure: Measure | None
    window_seconds: int
    raise_after: int
    clear_after: int
    min_samples: int
    rationale: str
    recommendation: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.window_seconds <= MAX_WINDOW_SECONDS:
            raise RuleDefinitionError(f"window_seconds must be 1 to {MAX_WINDOW_SECONDS}")
        for name in ("raise_after", "clear_after", "min_samples"):
            if not 1 <= getattr(self, name) <= MAX_CONSECUTIVE_EVALUATIONS:
                raise RuleDefinitionError(f"{name} must be 1 to {MAX_CONSECUTIVE_EVALUATIONS}")
        for name in ("rationale", "recommendation"):
            if not 0 < len(getattr(self, name).strip()) <= MAX_TEXT_CHARS:
                raise RuleDefinitionError(f"{name} must be 1 to {MAX_TEXT_CHARS} characters")
        if self.min_samples > self.window_seconds // SAMPLE_INTERVAL_S:
            # A window of w seconds holds w / 5 s samples: more could never be met.
            raise RuleDefinitionError("min_samples exceeds the samples the window can hold")
        if (self.measure is None) != (self.rule_type is RuleType.ABSENCE):
            raise RuleDefinitionError("only absence rules have no measure, and they all do")
        if self.measure is not None:
            is_ratio = self.measure.aggregation is Aggregation.RATIO
            if is_ratio != (self.rule_type is RuleType.AVAILABILITY_RATIO):
                raise RuleDefinitionError("the ratio aggregation is reserved to availability_ratio")
        # D-09: every level has a deadband, or clearing takes several evaluations.
        deadbands = self.measure is not None and all(
            lvl.has_deadband for lvl in self.measure.levels
        )
        if self.clear_after < 2 and not deadbands:
            raise RuleDefinitionError("no hysteresis: add a deadband or clear_after >= 2")


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """A rule as declared in configuration, before it is stored as a version."""

    key: str
    definition: RuleDefinition


@dataclass(frozen=True, slots=True)
class HealthRule:
    """One stored, immutable rule version. `unit` comes from the metric catalog."""

    id: uuid.UUID
    key: str
    version: int
    definition: RuleDefinition
    unit: str | None
    created_at: datetime

    def applies_to(self, component: Component) -> bool:
        return self.definition.enabled and self.definition.targets.applies_to(component)
