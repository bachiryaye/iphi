"""Loads `config/health_rules.yaml` into validated rule specs (ADR 0004, rules.md D-09, X-05)."""

from collections.abc import Collection, Iterable
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.health.domain.rules import (
    MAX_CONSECUTIVE_EVALUATIONS,
    MAX_TEXT_CHARS,
    MAX_WINDOW_SECONDS,
    RULE_KEY_PATTERN,
    Aggregation,
    FailureClass,
    Level,
    Measure,
    Operator,
    RuleDefinition,
    RuleDefinitionError,
    RuleSpec,
    RuleType,
    TargetSelector,
)
from app.ingestion.domain.catalog import MetricDefinition
from app.topology.domain import ComponentType

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "health_rules.yaml"
MAX_RULES = 100
MAX_FILE_BYTES = 256 * 1024


class RuleConfigError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Level(_Strict):
    threshold: float = Field(allow_inf_nan=False)
    clear: float = Field(allow_inf_nan=False)


class _Targets(_Strict):
    types: list[ComponentType] = Field(default_factory=list, max_length=len(ComponentType))
    components: list[str] = Field(default_factory=list, max_length=100)


class _Rule(_Strict):
    key: str = Field(pattern=RULE_KEY_PATTERN)
    type: RuleType
    failure_class: FailureClass
    metric: str | None = None
    aggregation: Aggregation | None = None
    window_s: int = Field(ge=1, le=MAX_WINDOW_SECONDS)
    operator: Operator | None = None
    warning: _Level | None = None
    critical: _Level | None = None
    targets: _Targets = Field(default_factory=_Targets)
    raise_after: int = Field(ge=1, le=MAX_CONSECUTIVE_EVALUATIONS)
    clear_after: int = Field(ge=1, le=MAX_CONSECUTIVE_EVALUATIONS)
    min_samples: int = Field(default=1, ge=1, le=MAX_CONSECUTIVE_EVALUATIONS)
    rationale: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    recommendation: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    enabled: bool = True


class _RuleFile(_Strict):
    rules: list[_Rule] = Field(min_length=1, max_length=MAX_RULES)


def load_rules(
    path: Path, catalog: Iterable[MetricDefinition], components: Collection[str]
) -> list[RuleSpec]:
    """Rule specs in file order; RuleConfigError names the faulty rule and reason. Targeted
    component keys must be among `components`, so a typo cannot silently apply to nothing."""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise RuleConfigError(f"{path.name} exceeds {MAX_FILE_BYTES} bytes")
    return parse_rules(path.read_text(encoding="utf-8"), catalog, components)


def parse_rules(
    text: str, catalog: Iterable[MetricDefinition], components: Collection[str]
) -> list[RuleSpec]:
    try:
        document = _RuleFile.model_validate(yaml.safe_load(text))
    except (yaml.YAMLError, ValidationError) as exc:
        raise RuleConfigError(f"invalid health rule file: {exc}") from exc
    metrics = {d.metric_name for d in catalog}
    keys = [r.key for r in document.rules]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise RuleConfigError(f"duplicate rule keys: {', '.join(duplicates)}")
    return [_spec(rule, metrics, components) for rule in document.rules]


def _spec(rule: _Rule, metrics: set[str], components: Collection[str]) -> RuleSpec:
    if rule.metric is not None and rule.metric not in metrics:
        raise RuleConfigError(f"{rule.key}: metric {rule.metric!r} is not in the catalog")
    unknown = sorted(k for k in rule.targets.components if k not in components)
    if unknown:
        raise RuleConfigError(f"{rule.key}: unknown target components {unknown}")
    try:
        return RuleSpec(rule.key, _definition(rule))
    except RuleDefinitionError as exc:
        raise RuleConfigError(f"{rule.key}: {exc}") from exc


def _definition(rule: _Rule) -> RuleDefinition:
    measured = (rule.metric, rule.aggregation, rule.operator)
    if rule.type is RuleType.ABSENCE:
        if any(v is not None for v in (*measured, rule.warning, rule.critical)):
            raise RuleDefinitionError("an absence rule has no metric, aggregation or thresholds")
        measure = None
    else:
        if rule.metric is None or rule.aggregation is None or rule.operator is None:
            raise RuleDefinitionError("a measured rule needs a metric, an aggregation, an operator")
        measure = Measure(
            rule.metric,
            rule.aggregation,
            rule.operator,
            _level(rule.warning),
            _level(rule.critical),
        )
    return RuleDefinition(
        rule_type=rule.type,
        failure_class=rule.failure_class,
        targets=TargetSelector(frozenset(rule.targets.types), frozenset(rule.targets.components)),
        measure=measure,
        window_seconds=rule.window_s,
        raise_after=rule.raise_after,
        clear_after=rule.clear_after,
        min_samples=rule.min_samples,
        rationale=rule.rationale,
        recommendation=rule.recommendation,
        enabled=rule.enabled,
    )


def _level(level: _Level | None) -> Level | None:
    return None if level is None else Level(level.threshold, level.clear)
