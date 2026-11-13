from dataclasses import replace

import pytest

from app.incidents.domain.lifecycle import (
    TRANSITIONS,
    Action,
    Closure,
    acknowledge,
    next_status,
    resolve,
)
from app.incidents.domain.model import (
    Actor,
    ActorType,
    EventType,
    IllegalTransitionError,
    Incident,
    IncidentStatus,
    Resolution,
)
from tests.health_rules import SLOT, T0
from tests.incident_builders import COLLECTOR, LATENCY, W, final, outcome, run

USER = Actor(ActorType.USER, "dev-local")
OPEN, ACK, RESOLVED = IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.RESOLVED


def opened() -> Incident:
    (incident,) = final(run([outcome(COLLECTOR, LATENCY, T0 + SLOT, W)]))
    return incident


@pytest.mark.parametrize(
    ("status", "action", "expected"),
    [
        (OPEN, Action.ACKNOWLEDGE, ACK),
        (OPEN, Action.RESOLVE, RESOLVED),
        (ACK, Action.RESOLVE, RESOLVED),
        (RESOLVED, Action.REOPEN, OPEN),
    ],
)
def test_legal_transitions_follow_the_table(
    status: IncidentStatus, action: Action, expected: IncidentStatus
) -> None:
    assert next_status(replace(opened(), status=status), action) is expected


@pytest.mark.parametrize(
    ("status", "action"),
    [(s, a) for s in IncidentStatus for a in Action if (s, a) not in TRANSITIONS],
)
def test_every_other_transition_is_illegal(status: IncidentStatus, action: Action) -> None:
    with pytest.raises(IllegalTransitionError):
        next_status(replace(opened(), status=status), action)


def test_acknowledging_twice_changes_nothing_the_second_time() -> None:
    first = acknowledge(opened(), USER, T0 + 10 * SLOT)
    second = acknowledge(first.incident, USER, T0 + 20 * SLOT)

    assert [e.type for e in first.events] == [EventType.ACKNOWLEDGED]
    assert second.events == ()
    assert second.incident.acknowledged_at == T0 + 10 * SLOT


def test_manual_resolution_needs_a_comment_and_records_it() -> None:
    incident = opened()
    with pytest.raises(ValueError, match="comment"):
        resolve(incident, Closure(Resolution.MANUAL, USER, T0 + 2 * SLOT, {}))

    change = resolve(
        incident, Closure(Resolution.MANUAL, USER, T0 + 2 * SLOT, {"comment": "Fixed upstream."})
    )

    assert change.incident.resolved_by == "dev-local"
    assert change.events[0].payload == {"resolution": "manual", "comment": "Fixed upstream."}
