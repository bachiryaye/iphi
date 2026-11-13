"""When a rule state calls for an incident, and which rules an incident's condition covers.

ADR 0005: an incident is resolved automatically once every rule it covers is back to Healthy,
and refused manual resolution while one of them still calls for it.
"""

from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType

from app.health.domain.records import RuleCondition
from app.health.domain.rules import FailureClass, HealthRule, RuleType
from app.health.domain.states import HealthState
from app.incidents.domain.model import IncidentSeverity
from app.topology.domain import Component

# ADR 0016: losing connectivity is part of being unreachable, not a second failure, so an
# availability incident also covers the component's connectivity rules until they recover.
_COVERAGE = MappingProxyType(
    {FailureClass.AVAILABILITY: frozenset({FailureClass.AVAILABILITY, FailureClass.CONNECTIVITY})}
)
# Upstream incidents of these classes absorb downstream alerts (ADR 0005).
SUPPRESSING = frozenset(
    {FailureClass.AVAILABILITY, FailureClass.CONNECTIVITY, FailureClass.TELEMETRY_LOSS}
)


def covered_classes(failure_class: FailureClass) -> frozenset[FailureClass]:
    return _COVERAGE.get(failure_class, frozenset({failure_class}))


def covered_rules(
    rules: Iterable[HealthRule], component: Component, failure_class: FailureClass
) -> list[HealthRule]:
    classes = covered_classes(failure_class)
    return [r for r in rules if r.applies_to(component) and r.definition.failure_class in classes]


def alert_severity(rule: HealthRule, condition: RuleCondition) -> IncidentSeverity | None:
    """Severity the rule's condition calls for; None when it calls for no incident.

    An absence rule Unknown without any observation in its window is silence: telemetry loss
    (ADR 0003). Silence never proves a failure (D-03), so telemetry loss is a warning.
    """
    if condition.state is HealthState.CRITICAL:
        return IncidentSeverity.CRITICAL
    if condition.state is HealthState.WARNING:
        return IncidentSeverity.WARNING
    silent = condition.state is HealthState.UNKNOWN and condition.raw_state is HealthState.UNKNOWN
    if rule.definition.rule_type is RuleType.ABSENCE and silent:
        return IncidentSeverity.WARNING
    return None


def condition_severity(
    covered: Sequence[HealthRule], conditions: Mapping[str, RuleCondition]
) -> IncidentSeverity | None:
    """Worst severity the covered rules call for, by rule key; None when none calls for one."""
    severities = [
        s
        for r in covered
        if (c := conditions.get(r.key)) is not None and (s := alert_severity(r, c)) is not None
    ]
    return max(severities, key=lambda s: s.rank, default=None)


def condition_cleared(
    covered: Sequence[HealthRule], conditions: Mapping[str, RuleCondition]
) -> bool:
    """Every covered rule is Healthy. Unknown is not recovery (D-02): the incident stays."""
    return bool(covered) and all(
        (c := conditions.get(r.key)) is not None and c.state is HealthState.HEALTHY for r in covered
    )


def alerting_rules(
    covered: Sequence[HealthRule], conditions: Mapping[str, RuleCondition]
) -> list[str]:
    return [
        r.key
        for r in covered
        if (c := conditions.get(r.key)) is not None and alert_severity(r, c) is not None
    ]
