"""Component state, impact annotation and platform aggregation (ADR 0004, rules.md D-05, D-06)."""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from app.health.domain.states import HealthState
from app.topology.domain import Component, Criticality, Dependency, upstream_ids

# Upstream states that annotate dependents as impacted (architecture §05.4).
IMPACTING = frozenset({HealthState.CRITICAL, HealthState.UNKNOWN})
_MAJOR = frozenset({Criticality.HIGH, Criticality.MEDIUM})


@dataclass(frozen=True, slots=True)
class RuleStanding:
    """Current debounced state of one rule on one component."""

    rule_key: str
    state: HealthState
    since: datetime


@dataclass(frozen=True, slots=True)
class ComponentVerdict:
    state: HealthState
    deciding_rule: str | None


@dataclass(frozen=True, slots=True)
class PlatformVerdict:
    state: HealthState
    priority: int | None
    rationale: str
    decided_by: tuple[uuid.UUID, ...]
    counts: Mapping[HealthState, int]


def component_verdict(standings: Iterable[RuleStanding]) -> ComponentVerdict:
    """Worst rule state; without any rule the component is Unknown, never Healthy (D-02).

    The deciding rule is the one that entered the worst state first, so the original cause
    stays named while later rules join it. A Healthy component has none: every rule agrees.
    """
    ranked = sorted(standings, key=lambda r: (-r.state.severity, r.since, r.rule_key))
    if not ranked:
        return ComponentVerdict(HealthState.UNKNOWN, None)
    top = ranked[0]
    return ComponentVerdict(top.state, None if top.state is HealthState.HEALTHY else top.rule_key)


def impacted_by(
    states: Mapping[uuid.UUID, HealthState], dependencies: Sequence[Dependency]
) -> dict[uuid.UUID, tuple[uuid.UUID, ...]]:
    """Transitive upstream components that are Critical or Unknown, per component.

    An annotation only (D-06): it never changes the impacted component's own state.
    """
    return {
        component_id: tuple(
            sorted(
                upstream
                for upstream in upstream_ids(component_id, dependencies)
                if states.get(upstream, HealthState.UNKNOWN) in IMPACTING
            )
        )
        for component_id in states
    }


def platform_verdict(
    components: Sequence[Component], states: Mapping[uuid.UUID, HealthState]
) -> PlatformVerdict:
    """Priority table of ADR 0004; never an average. A component without state is Unknown."""
    state_of = {c.id: states.get(c.id, HealthState.UNKNOWN) for c in components}
    counts = MappingProxyType({s: sum(v is s for v in state_of.values()) for s in HealthState})
    if not components:
        return PlatformVerdict(HealthState.UNKNOWN, None, "No component to evaluate.", (), counts)

    def having(state: HealthState, criticalities: frozenset[Criticality]) -> list[Component]:
        return [c for c in components if state_of[c.id] is state and c.criticality in criticalities]

    major_critical = having(HealthState.CRITICAL, _MAJOR)
    if major_critical:
        return _verdict(
            HealthState.CRITICAL,
            1,
            "a high- or medium-criticality component is Critical",
            major_critical,
            counts,
        )
    high_unknown = having(HealthState.UNKNOWN, frozenset({Criticality.HIGH}))
    if high_unknown:
        return _verdict(
            HealthState.UNKNOWN, 2, "a high-criticality component is Unknown", high_unknown, counts
        )
    degraded = [c for c in components if state_of[c.id] is not HealthState.HEALTHY]
    if degraded:
        return _verdict(
            HealthState.WARNING,
            3,
            "components are Warning, low-criticality Critical or medium/low-criticality Unknown",
            degraded,
            counts,
        )
    return PlatformVerdict(
        HealthState.HEALTHY,
        4,
        f"Priority 4: all {len(components)} components are Healthy.",
        (),
        counts,
    )


def _verdict(
    state: HealthState,
    priority: int,
    condition: str,
    deciding: Sequence[Component],
    counts: Mapping[HealthState, int],
) -> PlatformVerdict:
    names = ", ".join(sorted(c.key for c in deciding))
    return PlatformVerdict(
        state,
        priority,
        f"Priority {priority}: {condition} ({names}).",
        tuple(c.id for c in sorted(deciding, key=lambda c: c.key)),
        counts,
    )
