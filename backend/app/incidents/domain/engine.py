"""Incidents from one health pass (architecture §02.2 step 6, §05.5; ADR 0005; rules.md P-07).

A rule state only changes at a stored evaluation, so replaying the stored evaluations of a pass
replays every change it made. They are applied in sample-slot order and, within a slot, from
upstream to downstream components, availability rules first: an upstream incident opened at a
slot absorbs the downstream alerts of that slot, and an availability incident the connectivity
alert of its own component.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.observation import ObservationSource
from app.health.domain.records import EvaluationOutcome, RuleCondition
from app.health.domain.rules import FailureClass, HealthRule
from app.incidents.domain.conditions import (
    SUPPRESSING,
    alert_severity,
    condition_cleared,
    condition_severity,
    covered_rules,
)
from app.incidents.domain.lifecycle import (
    Change,
    Closure,
    Detection,
    Opening,
    change_severity,
    open_incident,
    reclassify_as_unreachable,
    record_occurrence,
    reopen,
    resolve,
    suppress_downstream,
)
from app.incidents.domain.model import (
    SYSTEM_ACTOR,
    EvidenceLink,
    EvidenceRef,
    EvidenceRole,
    Fingerprint,
    Impact,
    Incident,
    IncidentEvent,
    IncidentSeverity,
    Resolution,
)
from app.topology.domain import PlatformTopology, upstream_ids

# ADR 0005, in platform time: the same failure back within this delay reopens its incident.
REOPEN_WINDOW = timedelta(minutes=15)
_AFTER = timedelta(microseconds=1)


@dataclass(frozen=True, slots=True)
class IncidentPlan:
    """`reopenable`: the latest resolved incident of each fingerprint that may still reopen;
    `impacted`: components already attached to each active incident."""

    topology: PlatformTopology
    rules: Sequence[HealthRule]
    before: Mapping[tuple[uuid.UUID, str], RuleCondition]
    outcomes: Sequence[EvaluationOutcome]
    active: Sequence[Incident]
    reopenable: Sequence[Incident]
    impacted: Mapping[uuid.UUID, frozenset[uuid.UUID]]
    source: ObservationSource
    new_id: Callable[[], uuid.UUID]


@dataclass(frozen=True, slots=True)
class IncidentPass:
    """`opened`: new incidents to insert; `changed`: the final state of existing ones."""

    opened: tuple[Incident, ...]
    changed: tuple[Incident, ...]
    events: tuple[IncidentEvent, ...]
    evidence: tuple[EvidenceLink, ...]
    impacts: tuple[Impact, ...]


def process(plan: IncidentPlan) -> IncidentPass:
    run = _Pass(plan)
    for outcome in sorted(plan.outcomes, key=run.order):
        run.conditions[outcome.component_id][outcome.rule.key] = outcome.condition
        _apply(run, outcome)
    return run.result()


def reopenable_since(first_slot: datetime, history_start: datetime | None) -> datetime:
    """Resolution time from which an incident may still reopen during a pass from `first_slot`:
    within the reopen window, and never across a reset (ADR 0017)."""
    since = first_slot - REOPEN_WINDOW
    return since if history_start is None else max(since, history_start + _AFTER)


class _Pass:
    def __init__(self, plan: IncidentPlan) -> None:
        self.plan = plan
        self.conditions: dict[uuid.UUID, dict[str, RuleCondition]] = defaultdict(dict)
        for (component_id, rule_key), condition in plan.before.items():
            self.conditions[component_id][rule_key] = condition
        self.active = {i.fingerprint: i for i in plan.active}
        self.resolved = {i.fingerprint: i for i in plan.reopenable}
        self.impacted = {k: set(v) for k, v in plan.impacted.items()}
        self.components = {c.id: c for c in plan.topology.components}
        self.upstream = {
            c.id: upstream_ids(c.id, plan.topology.dependencies) for c in plan.topology.components
        }
        self.touched: dict[uuid.UUID, Incident] = {}
        self.created: set[uuid.UUID] = set()
        self.events: list[IncidentEvent] = []
        self.evidence: dict[tuple[uuid.UUID, EvidenceRef], EvidenceLink] = {}
        self.impacts: list[Impact] = []

    def order(self, o: EvaluationOutcome) -> tuple[datetime, int, int, str, str]:
        # A component has strictly more transitive dependencies than any of them.
        availability_first = o.rule.definition.failure_class is not FailureClass.AVAILABILITY
        return (
            o.evaluated_at,
            len(self.upstream[o.component_id]),
            int(availability_first),
            self.components[o.component_id].key,
            o.rule.key,
        )

    def fingerprint(self, component_id: uuid.UUID, failure_class: FailureClass) -> Fingerprint:
        return Fingerprint.of(self.plan.topology.platform_id, component_id, failure_class)

    def covered(self, incident: Incident) -> list[HealthRule]:
        component = self.components[incident.component_id]
        return covered_rules(self.plan.rules, component, incident.failure_class)

    def severity(self, incident: Incident) -> IncidentSeverity | None:
        return condition_severity(self.covered(incident), self.conditions[incident.component_id])

    def apply(self, change: Change) -> Incident:
        incident = change.incident
        self.touched[incident.id] = incident
        # A reclassified incident leaves its former fingerprint.
        for fingerprint in [f for f, i in self.active.items() if i.id == incident.id]:
            del self.active[fingerprint]
        self.events.extend(change.events)
        if incident.status.active:
            self.active[incident.fingerprint] = incident
            self.resolved.pop(incident.fingerprint, None)
        else:
            self.active.pop(incident.fingerprint, None)
            self.resolved[incident.fingerprint] = incident
        return incident

    def link(self, incident: Incident, o: EvaluationOutcome, role: EvidenceRole) -> None:
        """The evaluation and every observation it cites, so retention keeps them all."""
        refs = [
            EvidenceRef(evaluation_id=o.id),
            *(EvidenceRef(sample_id=i) for i in o.evidence.sample_ids),
            *(EvidenceRef(log_id=i) for i in o.evidence.log_ids),
        ]
        for ref in refs:
            link = EvidenceLink(incident.id, ref, role, o.evaluated_at)
            self.evidence.setdefault((incident.id, ref), link)

    def result(self) -> IncidentPass:
        return IncidentPass(
            opened=tuple(i for i in self.touched.values() if i.id in self.created),
            changed=tuple(i for i in self.touched.values() if i.id not in self.created),
            events=tuple(self.events),
            evidence=tuple(self.evidence.values()),
            impacts=tuple(self.impacts),
        )


def _apply(run: _Pass, o: EvaluationOutcome) -> None:
    severity = alert_severity(o.rule, o.condition)
    incident = _incident_for(run, o)
    if incident is not None:
        _update(run, incident, o, severity is not None)
    elif severity is not None:
        upstream = _suppressing(run, o)
        if upstream is None:
            _open(run, o, severity)
        else:
            _suppress(run, upstream, o)


def _incident_for(run: _Pass, o: EvaluationOutcome) -> Incident | None:
    """The active incident the outcome belongs to. Connectivity and availability of one
    component are one failure family: each joins the other's incident (ADR 0016, 0017)."""
    failure_class = o.rule.definition.failure_class
    own = run.active.get(run.fingerprint(o.component_id, failure_class))
    if own is not None:
        return own
    if failure_class is FailureClass.CONNECTIVITY:
        return run.active.get(run.fingerprint(o.component_id, FailureClass.AVAILABILITY))
    if failure_class is FailureClass.AVAILABILITY and alert_severity(o.rule, o.condition):
        degraded = run.active.get(run.fingerprint(o.component_id, FailureClass.CONNECTIVITY))
        if degraded is not None:
            key = run.components[o.component_id].key
            return run.apply(reclassify_as_unreachable(degraded, key, _detection(o)))
    return None


def _update(run: _Pass, incident: Incident, o: EvaluationOutcome, alerting: bool) -> None:
    detection = _detection(o)
    if alerting:
        incident = run.apply(record_occurrence(incident, detection))
        run.link(incident, o, EvidenceRole.SUPPORTING)
    elif condition_cleared(run.covered(incident), run.conditions[incident.component_id]):
        closure = Closure(
            Resolution.AUTO_RECOVERED, SYSTEM_ACTOR, o.evaluated_at, detection.payload()
        )
        run.apply(resolve(incident, closure))
        run.link(incident, o, EvidenceRole.RECOVERY)
        return
    target = run.severity(incident)
    if target is not None and target is not incident.severity:
        if not alerting:
            # The evaluation that lowered the severity justifies the change.
            run.link(incident, o, EvidenceRole.SUPPORTING)
        run.apply(change_severity(incident, target, detection))


def _suppressing(run: _Pass, o: EvaluationOutcome) -> Incident | None:
    upstream = run.upstream[o.component_id]
    candidates = [
        i
        for i in run.active.values()
        if i.component_id in upstream and i.failure_class in SUPPRESSING
    ]
    if o.rule.definition.failure_class is FailureClass.FRESHNESS:
        # ADR 0005: stale data under an upstream that recovered is a distinct freshness failure.
        candidates = [i for i in candidates if run.severity(i) is not None]
    return min(
        candidates, key=lambda i: (i.opened_at, run.components[i.component_id].key), default=None
    )


def _suppress(run: _Pass, incident: Incident, o: EvaluationOutcome) -> None:
    impacted = run.impacted.setdefault(incident.id, set())
    if o.component_id not in impacted:
        impacted.add(o.component_id)
        run.impacts.append(Impact(incident.id, o.component_id, o.evaluated_at))
        component = run.components[o.component_id]
        change = suppress_downstream(
            incident, (component.id, component.key), o.rule.definition.failure_class, _detection(o)
        )
        incident = run.apply(change)
    elif not o.sets_state:
        return
    run.link(incident, o, EvidenceRole.IMPACT)


def _open(run: _Pass, o: EvaluationOutcome, severity: IncidentSeverity) -> None:
    failure_class = o.rule.definition.failure_class
    fingerprint = run.fingerprint(o.component_id, failure_class)
    component = run.components[o.component_id]
    covered = covered_rules(run.plan.rules, component, failure_class)
    # Another covered rule may already alert more severely, unseen while it had no incident.
    severity = condition_severity(covered, run.conditions[o.component_id]) or severity
    previous = run.resolved.get(fingerprint)
    if previous is not None and _reopenable(previous, o.evaluated_at):
        incident = run.apply(reopen(previous, severity, _detection(o)))
    else:
        opening = Opening(
            run.plan.new_id(),
            run.plan.topology.platform_id,
            component.id,
            component.key,
            failure_class,
            severity,
            run.plan.source,
        )
        incident = run.apply(open_incident(opening, _detection(o)))
        run.created.add(incident.id)
    run.link(incident, o, EvidenceRole.TRIGGER)


def _reopenable(incident: Incident, at: datetime) -> bool:
    if incident.resolution is Resolution.RESET or incident.resolved_at is None:
        return False
    return at - incident.resolved_at <= REOPEN_WINDOW


def _detection(o: EvaluationOutcome) -> Detection:
    return Detection(o.id, o.rule.key, o.rule.version, o.evaluated_at)
