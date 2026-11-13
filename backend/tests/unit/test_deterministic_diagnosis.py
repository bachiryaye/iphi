import uuid

from app.core.observation import ObservationSource, Quality
from app.diagnostics.domain.deterministic import (
    DiagnosisInput,
    RelatedIncident,
    diagnose,
    evidence_set_hash,
    validate,
)
from app.diagnostics.domain.model import Citation, Claim, Uncertainty
from app.health.domain.evaluation import Evidence, Measurement
from app.health.domain.records import StoredEvaluation
from app.health.domain.rules import HealthRule
from app.incidents.domain.model import EvidenceRole
from app.incidents.domain.records import EvidenceItem, StoredEvidence
from app.ingestion.domain.observations import SampleDetail
from tests.health_rules import SLOT, T0
from tests.incident_builders import AVAIL, COLLECTOR, FRESH, HISTORIAN, C, W, final, outcome, run

KEYS = {COLLECTOR.id: COLLECTOR.key, HISTORIAN.id: HISTORIAN.key}


def evaluation_item(
    ordinal: int,
    role: EvidenceRole,
    component_id: uuid.UUID,
    rule: HealthRule = AVAIL,
    sample_id: int = 900,
) -> EvidenceItem:
    evaluation = StoredEvaluation(
        id=100 + ordinal,
        rule=rule,
        component_id=component_id,
        evaluated_at=T0 + ordinal * SLOT,
        window_start=T0,
        measurement=Measurement(C, 0.0, 1, Evidence((sample_id,)), "last of up = 0"),
        state=C,
    )
    stored = StoredEvidence(ordinal, ordinal, role, T0 + ordinal * SLOT, evaluation.id, None, None)
    return EvidenceItem(stored, evaluation, None, None)


def sample_item(ordinal: int, sample_id: int) -> EvidenceItem:
    sample = SampleDetail(
        sample_id,
        COLLECTOR.id,
        "up",
        0.0,
        "bool",
        Quality.GOOD,
        T0,
        ObservationSource.SIMULATION,
        None,
    )
    stored = StoredEvidence(ordinal, ordinal, EvidenceRole.TRIGGER, T0, None, sample_id, None)
    return EvidenceItem(stored, None, sample, None)


def collector_input(related: tuple[RelatedIncident, ...] = ()) -> DiagnosisInput:
    (incident,) = final(run([outcome(COLLECTOR, AVAIL, T0 + SLOT, C)]))
    return DiagnosisInput(
        incident=incident,
        component_keys=KEYS,
        evidence=[
            evaluation_item(1, EvidenceRole.TRIGGER, COLLECTOR.id),
            sample_item(2, 900),
            evaluation_item(3, EvidenceRole.IMPACT, HISTORIAN.id, FRESH, 901),
        ],
        impacted=["historian-01"],
        related=related,
        logs_attached=False,
    )


def test_facts_cite_the_trigger_evaluation_and_its_samples() -> None:
    diagnosis = diagnose(collector_input())

    first = diagnosis.observed_facts[0]
    assert "R-AVAIL-001 v1 on collector-01" in first.text
    assert [c.label for c in first.citations] == ["E1", "E2"]


def test_hypothesis_is_a_correlation_on_the_most_upstream_component() -> None:
    (hypothesis,) = diagnose(collector_input()).hypotheses

    assert hypothesis.uncertainty is Uncertainty.LOW
    assert "correlated" in hypothesis.text
    assert "causation is not proven" in hypothesis.text
    assert "caused by" not in hypothesis.text
    assert {c.label for c in hypothesis.citations} == {"E1", "E2", "E3"}


def test_upstream_incident_is_named_first_when_one_overlaps() -> None:
    (upstream,) = final(run([outcome(COLLECTOR, AVAIL, T0, W)]))
    related = (RelatedIncident(upstream, "edge-gateway-01", 1),)

    diagnosis = diagnose(collector_input(related))

    assert "edge-gateway-01" in diagnosis.hypotheses[0].text
    assert diagnosis.recommended_checks[0].text.startswith("Investigate")


def test_limitations_state_simulation_and_missing_logs() -> None:
    limitations = " ".join(diagnose(collector_input()).limitations)

    assert "Simulated environment" in limitations
    assert "No log evidence" in limitations


def test_validation_drops_citations_outside_the_evidence_set() -> None:
    diagnosis = diagnose(collector_input())
    forged = Claim("Invented.", (Citation(999, "E99"),))
    tampered = diagnosis.__class__(
        (*diagnosis.observed_facts, forged),
        diagnosis.hypotheses,
        diagnosis.recommended_checks,
        diagnosis.limitations,
        diagnosis.model,
    )

    valid, report = validate(tampered, {1, 2, 3})

    assert forged not in valid.observed_facts
    assert report.removed == ("Invented.",)
    assert report.dropped_citations == 1


def test_same_input_gives_the_same_evidence_set_hash() -> None:
    data = collector_input()

    assert evidence_set_hash(data) == evidence_set_hash(data)
