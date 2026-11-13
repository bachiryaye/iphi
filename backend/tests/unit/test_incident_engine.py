from dataclasses import replace
from datetime import datetime

from hypothesis import given
from hypothesis import strategies as st

from app.health.domain.records import RuleCondition
from app.health.domain.rules import FailureClass
from app.health.domain.states import HealthState
from app.incidents.domain.engine import REOPEN_WINDOW
from app.incidents.domain.model import (
    EventType,
    EvidenceRole,
    IncidentSeverity,
    IncidentStatus,
    Resolution,
)
from tests.health_rules import SLOT, T0
from tests.incident_builders import (
    AVAIL,
    COLLECTOR,
    CONN,
    FRESH,
    HISTORIAN,
    LATENCY,
    TELEMETRY,
    C,
    H,
    U,
    W,
    final,
    outcome,
    periodic,
    run,
)


def at(slot: int) -> datetime:
    return T0 + slot * SLOT


def test_first_alert_opens_an_incident_with_its_trigger_evidence() -> None:
    o = outcome(COLLECTOR, LATENCY, at(1), W)

    result = run([o])

    (incident,) = result.opened
    assert (incident.failure_class, incident.severity, incident.occurrence_count) == (
        FailureClass.LATENCY,
        IncidentSeverity.WARNING,
        1,
    )
    assert [e.type for e in result.events] == [EventType.OPENED]
    refs = {(link.ref.evaluation_id, link.ref.sample_id, link.role) for link in result.evidence}
    assert refs == {
        (o.id, None, EvidenceRole.TRIGGER),
        (None, o.evidence.sample_ids[0], EvidenceRole.TRIGGER),
    }


def test_repeated_alerts_update_one_incident_instead_of_a_storm() -> None:
    first = outcome(COLLECTOR, LATENCY, at(1), W)
    outcomes = [first, *(periodic(outcome(COLLECTOR, LATENCY, at(i), W)) for i in range(2, 21))]

    result = run(outcomes)

    (incident,) = final(result)
    assert incident.occurrence_count == 20
    assert [e.type for e in result.events].count(EventType.OCCURRENCE) == 19


def test_severity_follows_the_worst_alerting_rule_and_keeps_its_peak() -> None:
    result = run(
        [
            outcome(COLLECTOR, LATENCY, at(1), W),
            outcome(COLLECTOR, LATENCY, at(2), C),
            outcome(COLLECTOR, LATENCY, at(3), W),
        ]
    )

    (incident,) = final(result)
    assert (incident.severity, incident.peak_severity) == (
        IncidentSeverity.WARNING,
        IncidentSeverity.CRITICAL,
    )
    changes = [e.payload for e in result.events if e.type is EventType.SEVERITY_CHANGED]
    assert [(p["from"], p["to"]) for p in changes] == [
        ("warning", "critical"),
        ("critical", "warning"),
    ]


def test_availability_incident_resolves_once_connectivity_also_recovered() -> None:
    first = run(
        [
            outcome(COLLECTOR, AVAIL, at(1), C),
            outcome(COLLECTOR, CONN, at(2), W),
            outcome(COLLECTOR, AVAIL, at(5), H),
        ]
    )
    (open_incident,) = final(first)
    assert open_incident.status is IncidentStatus.OPEN
    assert open_incident.severity is IncidentSeverity.WARNING

    before = {(COLLECTOR.id, AVAIL.key): RuleCondition(H, H)}
    second = run([outcome(COLLECTOR, CONN, at(60), H)], active=[open_incident], before=before)

    (resolved,) = second.changed
    assert (resolved.status, resolved.resolution) == (
        IncidentStatus.RESOLVED,
        Resolution.AUTO_RECOVERED,
    )
    assert {link.role for link in second.evidence} == {EvidenceRole.RECOVERY}


def test_unknown_is_not_recovery() -> None:
    result = run([outcome(COLLECTOR, LATENCY, at(1), C), outcome(COLLECTOR, LATENCY, at(4), U)])

    (incident,) = final(result)
    assert incident.status is IncidentStatus.OPEN


def test_telemetry_loss_needs_silence_not_a_confirming_unknown() -> None:
    confirming = run([outcome(COLLECTOR, TELEMETRY, at(1), U, H)])
    silent = run([outcome(COLLECTOR, TELEMETRY, at(1), U, U)])

    assert final(confirming) == []
    (incident,) = final(silent)
    assert (incident.failure_class, incident.severity) == (
        FailureClass.TELEMETRY_LOSS,
        IncidentSeverity.WARNING,
    )


def test_downstream_alert_is_attached_to_the_upstream_outage_in_the_same_slot() -> None:
    # Listed downstream first: processing still goes upstream first within a slot.
    result = run([outcome(HISTORIAN, LATENCY, at(1), W), outcome(COLLECTOR, AVAIL, at(1), C)])

    (incident,) = result.opened
    assert incident.component_id == COLLECTOR.id
    assert [(i.component_id, i.incident_id) for i in result.impacts] == [
        (HISTORIAN.id, incident.id)
    ]
    assert EventType.DOWNSTREAM_SUPPRESSED in [e.type for e in result.events]
    assert EvidenceRole.IMPACT in {link.role for link in result.evidence}


def test_stale_data_under_a_recovered_upstream_is_its_own_incident() -> None:
    upstream = final(run([outcome(COLLECTOR, AVAIL, at(1), C)]))
    before = {(COLLECTOR.id, AVAIL.key): RuleCondition(U, U)}

    result = run([outcome(HISTORIAN, FRESH, at(10), W)], active=upstream, before=before)

    (incident,) = result.opened
    assert (incident.component_id, incident.failure_class) == (
        HISTORIAN.id,
        FailureClass.FRESHNESS,
    )


def test_connectivity_incident_is_reclassified_when_the_component_stops_answering() -> None:
    result = run([outcome(COLLECTOR, CONN, at(1), W), outcome(COLLECTOR, AVAIL, at(2), C)])

    (incident,) = final(result)
    assert (incident.failure_class, incident.severity, incident.title) == (
        FailureClass.AVAILABILITY,
        IncidentSeverity.CRITICAL,
        "collector-01 unreachable",
    )
    assert EventType.RECLASSIFIED in [e.type for e in result.events]


def test_same_failure_reopens_within_the_window_and_opens_anew_beyond_it() -> None:
    first = run([outcome(COLLECTOR, LATENCY, at(1), W), outcome(COLLECTOR, LATENCY, at(4), H)])
    (resolved,) = final(first)
    assert resolved.resolved_at is not None
    within = resolved.resolved_at + REOPEN_WINDOW
    beyond = within + SLOT

    reopened = run([outcome(COLLECTOR, LATENCY, within, W)], reopenable=[resolved])
    fresh = run([outcome(COLLECTOR, LATENCY, beyond, W)], reopenable=[resolved])

    (incident,) = reopened.changed
    assert (incident.id, incident.status, incident.reopen_count) == (
        resolved.id,
        IncidentStatus.OPEN,
        1,
    )
    (new,) = fresh.opened
    assert new.id != resolved.id


def test_incident_closed_by_a_reset_never_reopens() -> None:
    first = run([outcome(COLLECTOR, LATENCY, at(1), W), outcome(COLLECTOR, LATENCY, at(4), H)])
    (resolved,) = final(first)
    reset = replace(resolved, resolution=Resolution.RESET)

    result = run([outcome(COLLECTOR, LATENCY, at(5), W)], reopenable=[reset])

    assert len(result.opened) == 1


def test_transitions_are_never_dated_before_the_latest_change() -> None:
    (incident,) = final(run([outcome(COLLECTOR, LATENCY, at(10), W)]))
    acknowledged = replace(
        incident,
        status=IncidentStatus.ACKNOWLEDGED,
        acknowledged_at=at(20),
        acknowledged_by="dev-local",
        updated_at=at(20),
    )

    result = run([outcome(COLLECTOR, LATENCY, at(12), H)], active=[acknowledged])

    (resolved,) = result.changed
    assert resolved.resolved_at == at(20)


@given(st.lists(st.sampled_from([H, W, C, U]), min_size=1, max_size=60))
def test_any_state_sequence_keeps_one_incident_per_failure_within_the_window(
    states: list[HealthState],
) -> None:
    outcomes = [outcome(COLLECTOR, LATENCY, at(i), s) for i, s in enumerate(states, start=1)]
    assert len(states) * SLOT < REOPEN_WINDOW

    result = run(outcomes)

    assert len(result.opened) <= 1
    alerting = [s for s in states if s in (W, C)]
    (incident,) = result.opened or (None,)
    if incident is None:
        assert alerting == []
    else:
        current = final(result)[0]
        assert current.occurrence_count == len(alerting)
        last_known = [s for s in states if s is not U]
        assert (current.status is IncidentStatus.RESOLVED) == (last_known[-1] is H)
