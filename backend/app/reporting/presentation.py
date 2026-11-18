import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.diagnostics.domain.model import Hypothesis, StoredDiagnostic
from app.incidents.domain.records import EvidenceItem
from app.reporting.domain import ReportSnapshot

type Row = dict[str, str]


def utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@dataclass(frozen=True, slots=True)
class ReportView:
    snapshot: ReportSnapshot
    records: tuple[Row, ...]

    def group(self, kind: str) -> tuple[Row, ...]:
        return tuple(row for row in self.records if row["record_type"] == kind)

    def claims(self, diagnostic_id: UUID) -> tuple[Row, ...]:
        return tuple(
            row
            for row in self.records
            if row.get("diagnostic_id") == str(diagnostic_id) and row["record_type"] == "diagnostic"
        )


def present(snapshot: ReportSnapshot) -> ReportView:
    incident = snapshot.facts.summary.incident
    common = {
        "environment": "simulation",
        "incident_id": str(incident.id),
        "incident_reference": incident.reference,
        "snapshot_at_utc": utc(snapshot.generated_at),
    }
    return ReportView(snapshot, tuple({**common, **row} for row in _records(snapshot)))


def _records(snapshot: ReportSnapshot) -> Iterator[Row]:
    facts = snapshot.facts
    incident = facts.summary.incident
    keys = snapshot.topology.keys_by_id()
    summary = {
        "Title": incident.title,
        "Platform": snapshot.topology.name,
        "Component": keys[incident.component_id],
        "Status": incident.status.value,
        "Severity": incident.severity.value,
        "Peak severity": incident.peak_severity.value,
        "Failure class": incident.failure_class.value,
        "Source": incident.source.value,
        "Opened UTC": utc(incident.opened_at),
        "Last seen UTC": utc(incident.last_seen_at),
        "Resolved UTC": utc(incident.resolved_at) if incident.resolved_at else "Unresolved",
        "Resolution": incident.resolution.value if incident.resolution else "None",
        "Occurrences": str(incident.occurrence_count),
        "Reopens": str(incident.reopen_count),
        "Evidence items": str(facts.summary.evidence_count),
        "Events": str(facts.event_count),
        "Fingerprint": incident.fingerprint.value,
        "Scenario run": str(incident.scenario_run_id) if incident.scenario_run_id else "None",
        "Impacted components": ", ".join(keys[item.component_id] for item in facts.summary.impacts)
        or "None",
    }
    for name, value in summary.items():
        yield {"record_type": "summary", "type": name, "text": value}
    for event in facts.events:
        yield {
            "record_type": "event",
            "id": str(event.id),
            "type": event.event.type.value,
            "occurred_at_utc": utc(event.event.occurred_at),
            "text": event.event.actor.label,
            "details": json_text(event.event.payload),
            "source": incident.source.value,
        }
    rules = {}
    for item in facts.evidence:
        row = _evidence(item, keys)
        yield {"record_type": "evidence", **row}
        if item.evaluation is not None:
            rule = item.evaluation.rule
            rules[rule.id] = rule
    for rule in sorted(rules.values(), key=lambda r: (r.key, r.version)):
        definition = rule.definition
        measure = definition.measure
        levels = {}
        if measure:
            levels = {
                name: {"threshold": level.threshold, "clear": level.clear}
                for name, level in (("warning", measure.warning), ("critical", measure.critical))
                if level is not None
            }
        yield {
            "record_type": "rule",
            "id": str(rule.id),
            "rule_key": rule.key,
            "rule_version": str(rule.version),
            "metric": measure.metric_name if measure else "any observation",
            "unit": rule.unit or "",
            "text": definition.rationale,
            "recommendation": definition.recommendation,
            "details": json_text(
                {
                    "type": definition.rule_type.value,
                    "window_seconds": definition.window_seconds,
                    "aggregation": measure.aggregation.value if measure else "absence",
                    "operator": measure.operator.value if measure else "absence",
                    "levels": levels,
                    "raise_after": definition.raise_after,
                    "clear_after": definition.clear_after,
                    "min_samples": definition.min_samples,
                }
            ),
        }
    for diagnostic in snapshot.diagnostics:
        yield from _diagnosis(diagnostic)


def _evidence(item: EvidenceItem, keys: Mapping[UUID, str]) -> Row:
    row = {
        "id": str(item.stored.id),
        "label": item.label,
        "role": item.stored.role.value,
        "added_at_utc": utc(item.stored.added_at),
    }
    if (evaluation := item.evaluation) is not None:
        measurement = evaluation.measurement
        row.update(
            type="evaluation",
            observation_id=str(evaluation.id),
            component=keys[evaluation.component_id],
            occurred_at_utc=utc(evaluation.evaluated_at),
            rule_key=evaluation.rule.key,
            rule_version=str(evaluation.rule.version),
            metric=evaluation.rule.definition.measure.metric_name
            if evaluation.rule.definition.measure
            else "any observation",
            value="" if measurement.observed_value is None else str(measurement.observed_value),
            unit=evaluation.rule.unit or "",
            state=evaluation.state.value,
            text=measurement.explanation,
            source="simulation",
            details=json_text(
                {
                    "window_start_exclusive": utc(evaluation.window_start),
                    "window_end_inclusive": utc(evaluation.evaluated_at),
                    "sample_count": measurement.sample_count,
                    "raw_state": measurement.raw_state.value,
                    "sample_ids": measurement.evidence.sample_ids,
                    "log_ids": measurement.evidence.log_ids,
                }
            ),
        )
    elif (sample := item.sample) is not None:
        row.update(
            type="sample",
            observation_id=str(sample.id),
            component=keys[sample.component_id],
            occurred_at_utc=utc(sample.observed_at),
            metric=sample.metric_name,
            value=str(sample.value),
            unit=sample.unit,
            quality=sample.quality.value,
            source=sample.source.value,
            scenario_run_id=str(sample.scenario_run_id or ""),
        )
    elif (event := item.log) is not None:
        row.update(
            type="log",
            observation_id=str(event.id),
            component=keys[event.component_id],
            occurred_at_utc=utc(event.observed_at),
            state=event.severity.value,
            text=event.message,
            source=event.source.value,
            details=json_text(event.attributes),
            scenario_run_id=str(event.scenario_run_id or ""),
        )
    return row


def _diagnosis(diagnostic: StoredDiagnostic) -> Iterator[Row]:
    common = {
        "diagnostic_id": str(diagnostic.id),
        "diagnosis_kind": diagnostic.kind.value,
        "model": diagnostic.model,
        "status": diagnostic.status.value,
        "occurred_at_utc": utc(diagnostic.created_at),
        "provider": diagnostic.provider,
        "error_code": diagnostic.error_code or "",
        "deterministic_id": str(diagnostic.deterministic_id or ""),
        "evidence_set_hash": diagnostic.evidence_set_hash,
    }
    yield {
        **common,
        "record_type": "diagnostic_meta",
        "type": "Diagnosis",
        "text": "AI-generated — verify against evidence"
        if diagnostic.kind.value == "llm"
        else "Deterministic diagnosis",
        "details": json_text(
            {
                "checked_claims": diagnostic.validation.checked_claims,
                "dropped_citations": diagnostic.validation.dropped_citations,
                "fake_provider": diagnostic.provider == "fake",
                "created_by": diagnostic.created_by,
            }
        ),
    }
    sections = (
        ("Fact", diagnostic.diagnosis.observed_facts),
        ("Hypothesis", diagnostic.diagnosis.hypotheses),
        ("Check", diagnostic.diagnosis.recommended_checks),
    )
    for name, claims in sections:
        for claim in claims:
            yield {
                **common,
                "record_type": "diagnostic",
                "type": name,
                "text": claim.text,
                "evidence_ids": "; ".join(f"{c.label} (#{c.evidence_id})" for c in claim.citations),
                "uncertainty": claim.uncertainty.value if isinstance(claim, Hypothesis) else "",
            }
    for name, values in (
        ("Limitation", diagnostic.diagnosis.limitations),
        ("Removed: unsupported", diagnostic.validation.removed),
    ):
        for value in values:
            yield {**common, "record_type": "diagnostic", "type": name, "text": value}
