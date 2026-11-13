"""Deterministic diagnosis (architecture §05.7, ADR 0006; rules.md P-07, D-19, D-20).

Facts are the stored evaluations behind the incident; the hypothesis names the most upstream
component in fault along the dependency graph, worded as a correlation; checks are the
recommendations of the rules involved. It is the mandatory fallback of any LLM diagnosis.
"""

import hashlib
import json
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.diagnostics.domain.model import (
    Citation,
    Claim,
    Diagnosis,
    Hypothesis,
    Uncertainty,
    ValidationReport,
)
from app.health.domain.records import StoredEvaluation
from app.incidents.domain.model import EvidenceRole, Incident
from app.incidents.domain.records import PACKED_OBSERVATIONS, EvidenceItem

MODEL = "iphi/deterministic-v1"
PROVIDER = "iphi"
MAX_FACTS = 12


@dataclass(frozen=True, slots=True)
class RelatedIncident:
    """An incident on an upstream component, active while this one was. `depth`: how many
    transitive dependencies its component has (fewer = further upstream)."""

    incident: Incident
    component_key: str
    depth: int


@dataclass(frozen=True, slots=True)
class _Evaluated:
    """An evidence row that references a rule evaluation, with that evaluation."""

    item: EvidenceItem
    evaluation: StoredEvaluation


@dataclass(frozen=True, slots=True)
class DiagnosisInput:
    incident: Incident
    component_keys: Mapping[uuid.UUID, str]
    evidence: Sequence[EvidenceItem]
    impacted: Sequence[str]
    related: Sequence[RelatedIncident]
    logs_attached: bool


def diagnose(data: DiagnosisInput) -> Diagnosis:
    incident = data.incident
    component = data.component_keys[incident.component_id]
    evaluations = [_Evaluated(i, i.evaluation) for i in data.evidence if i.evaluation is not None]
    triggers = _with_role(evaluations, EvidenceRole.TRIGGER)
    impacts = _latest_per_component(_with_role(evaluations, EvidenceRole.IMPACT))
    trigger_cites = _cite(data, triggers)
    facts = [
        Claim(f"{_rule(i)} on {_component(data, i)}: {_explanation(i)}", _cite(data, [i]))
        for i in triggers
    ]
    latest = _latest_per_rule(_with_role(evaluations, EvidenceRole.SUPPORTING))
    facts += [
        Claim(
            f"Latest {_rule(i)} evaluation on {_component(data, i)} "
            f"({_time(i.item.stored.added_at)}): {_explanation(i)}",
            _cite(data, [i]),
        )
        for i in latest
    ]
    end = incident.resolved_at or incident.last_seen_at
    facts.append(
        Claim(
            f"{incident.occurrence_count} stored evaluations confirmed the condition between "
            f"{_time(incident.opened_at)} and {_time(incident.last_seen_at)}.",
            _unique(trigger_cites + _cite(data, latest)),
        )
    )
    facts += [
        Claim(f"Downstream {_component(data, i)}, {_rule(i)}: {_explanation(i)}", _cite(data, [i]))
        for i in impacts
    ]
    if not incident.status.active:
        recoveries = _with_role(evaluations, EvidenceRole.RECOVERY)
        facts += [
            Claim(
                f"Recovered at {_time(i.item.stored.added_at)}: {_rule(i)} {_explanation(i)}",
                _cite(data, [i]),
            )
            for i in recoveries[-1:]
        ]
    return Diagnosis(
        observed_facts=tuple(facts[:MAX_FACTS]),
        hypotheses=(_hypothesis(data, component, trigger_cites, impacts),),
        recommended_checks=_checks(data, component, [*triggers, *latest], trigger_cites),
        limitations=_limitations(data, end),
        model=MODEL,
    )


def _hypothesis(
    data: DiagnosisInput,
    component: str,
    trigger_cites: tuple[Citation, ...],
    impacts: Sequence[_Evaluated],
) -> Hypothesis:
    upstream = _most_upstream(data.related)
    if upstream is not None:
        return Hypothesis(
            f"{component} depends on {upstream.component_key}, where incident "
            f"{upstream.incident.reference} ({upstream.incident.failure_class}) was active from "
            f"{_time(upstream.incident.opened_at)}. The condition on {component} is correlated "
            "with it along the dependency graph; causation is not proven.",
            trigger_cites,
            Uncertainty.MEDIUM,
        )
    if data.impacted:
        return Hypothesis(
            f"{component} is the most upstream component in fault in this incident; the "
            f"degradation of {', '.join(data.impacted)} downstream is correlated with it. "
            "Correlation along the dependency graph; causation is not proven.",
            _unique(trigger_cites + _cite(data, impacts)),
            Uncertainty.LOW,
        )
    return Hypothesis(
        f"No upstream component of {component} had an incident overlapping this one: the "
        f"condition is most likely local to {component}. Correlation only; causation is not "
        "proven.",
        trigger_cites,
        Uncertainty.MEDIUM,
    )


def _checks(
    data: DiagnosisInput,
    component: str,
    evaluations: Sequence[_Evaluated],
    trigger_cites: tuple[Citation, ...],
) -> tuple[Claim, ...]:
    checks: list[Claim] = []
    upstream = _most_upstream(data.related)
    if upstream is not None:
        checks.append(
            Claim(
                f"Investigate {upstream.incident.reference} on {upstream.component_key} first: "
                f"it is upstream of {component}.",
                trigger_cites,
            )
        )
    seen: set[str] = set()
    for e in evaluations:
        recommendation = e.evaluation.rule.definition.recommendation
        if recommendation not in seen:
            seen.add(recommendation)
            checks.append(Claim(f"{recommendation} ({_rule(e)})", _cite(data, [e])))
    return tuple(checks)


def _limitations(data: DiagnosisInput, end: datetime) -> tuple[str, ...]:
    incident = data.incident
    limitations = [
        "Simulated environment: every observation comes from the IPHI simulator, not from a "
        "real system.",
        f"Observed window: {_time(incident.opened_at)} to {_time(end)}; nothing outside it was "
        "considered.",
        "Correlation in time along the dependency graph only; no causal evidence is available.",
    ]
    if not data.logs_attached:
        limitations.append("No log evidence is attached to this incident.")
    if incident.status.active:
        limitations.append(
            f"The incident is still {incident.status}: evidence after "
            f"{_time(incident.last_seen_at)} is not considered."
        )
    return tuple(limitations)


def validate(diagnosis: Diagnosis, evidence_ids: set[int]) -> tuple[Diagnosis, ValidationReport]:
    """Keeps only citations of the incident's evidence set; drops claims left without any."""
    removed: list[str] = []
    dropped = 0

    def kept(citations: tuple[Citation, ...]) -> tuple[Citation, ...]:
        nonlocal dropped
        valid = tuple(c for c in citations if c.evidence_id in evidence_ids)
        dropped += len(citations) - len(valid)
        return valid

    def claims(items: Iterable[Claim]) -> tuple[Claim, ...]:
        result = []
        for claim in items:
            citations = kept(claim.citations)
            if citations:
                result.append(Claim(claim.text, citations))
            else:
                removed.append(claim.text)
        return tuple(result)

    hypotheses = []
    for h in diagnosis.hypotheses:
        citations = kept(h.citations)
        if citations:
            hypotheses.append(Hypothesis(h.text, citations, h.uncertainty))
        else:
            removed.append(h.text)
    checked = (
        len(diagnosis.observed_facts)
        + len(diagnosis.hypotheses)
        + len(diagnosis.recommended_checks)
    )
    valid = Diagnosis(
        claims(diagnosis.observed_facts),
        tuple(hypotheses),
        claims(diagnosis.recommended_checks),
        diagnosis.limitations,
        diagnosis.model,
    )
    return valid, ValidationReport(checked, tuple(removed), dropped)


def evidence_set_hash(data: DiagnosisInput) -> str:
    """Identifies what the diagnosis was computed from: same input, same diagnosis."""
    material = {
        "model": MODEL,
        "evidence": sorted(i.stored.id for i in data.evidence),
        "related": sorted([r.incident.reference, r.incident.status.value] for r in data.related),
        "impacted": sorted(data.impacted),
        "incident": [data.incident.status.value, data.incident.occurrence_count],
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _most_upstream(related: Sequence[RelatedIncident]) -> RelatedIncident | None:
    return min(related, key=lambda r: (r.depth, r.incident.opened_at), default=None)


def _with_role(items: Sequence[_Evaluated], role: EvidenceRole) -> list[_Evaluated]:
    return sorted((e for e in items if e.item.stored.role is role), key=lambda e: e.item.stored.id)


def _latest_per_rule(items: Sequence[_Evaluated]) -> list[_Evaluated]:
    latest = {_rule(e): e for e in items}
    return sorted(latest.values(), key=lambda e: e.item.stored.id)


def _latest_per_component(items: Sequence[_Evaluated]) -> list[_Evaluated]:
    latest = {e.evaluation.component_id: e for e in items}
    return sorted(latest.values(), key=lambda e: e.item.stored.id)


def _cite(data: DiagnosisInput, items: Iterable[_Evaluated]) -> tuple[Citation, ...]:
    """Each evaluation with the observations it cites, as far as they are evidence."""
    by_sample = {i.sample.id: i for i in data.evidence if i.sample is not None}
    by_log = {i.log.id: i for i in data.evidence if i.log is not None}
    citations: list[Citation] = []
    for e in items:
        citations.append(Citation(e.item.stored.id, e.item.label))
        cited = e.evaluation.measurement.evidence
        for found in [by_sample.get(s) for s in cited.sample_ids[:PACKED_OBSERVATIONS]] + [
            by_log.get(lg) for lg in cited.log_ids[:PACKED_OBSERVATIONS]
        ]:
            if found is not None:
                citations.append(Citation(found.stored.id, found.label))
    return _unique(tuple(citations))


def _unique(citations: tuple[Citation, ...]) -> tuple[Citation, ...]:
    return tuple(dict.fromkeys(citations))


def _rule(e: _Evaluated) -> str:
    return f"{e.evaluation.rule.key} v{e.evaluation.rule.version}"


def _component(data: DiagnosisInput, e: _Evaluated) -> str:
    return data.component_keys.get(e.evaluation.component_id, "unknown component")


def _explanation(e: _Evaluated) -> str:
    return e.evaluation.measurement.explanation


def _time(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
