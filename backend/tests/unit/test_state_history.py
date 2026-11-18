from datetime import UTC, datetime, timedelta

from app.health.domain.history import (
    HistoryData,
    HistoryPoint,
    HistoryPolicy,
    HistoryTail,
    StateHistory,
    state_history,
)
from app.health.domain.states import HealthState as S
from app.ingestion.domain.series import TimeWindow

AT = datetime(2026, 11, 18, tzinfo=UTC)


def at(seconds: float) -> datetime:
    return AT + timedelta(seconds=seconds)


def point(seconds: int, state: S, key: str = "rule", version: int = 1) -> HistoryPoint:
    return HistoryPoint(key, version, at(seconds), state, seconds + 1)


def history(
    points: list[HistoryPoint],
    *,
    end: int = 180,
    bins: int = 500,
    reset: int | None = None,
    tails: tuple[HistoryTail, ...] = (),
) -> StateHistory:
    return state_history(
        HistoryData(points, tails, [("rule", 1)], None if reset is None else at(reset)),
        HistoryPolicy(TimeWindow(at(0), at(end)), bins, timedelta(seconds=20)),
    )


def test_empty_history_is_unknown_with_complete_coverage() -> None:
    result = history([])
    for lane in (result.component, *result.rules):
        (segment,) = lane.segments
        assert (segment.start, segment.end, segment.state, segment.evaluation_ids) == (
            at(0),
            at(180),
            S.UNKNOWN,
            (),
        )


def test_recorded_minute_watermarks_support_continuity_but_gaps_do_not() -> None:
    result = history([point(0, S.HEALTHY), point(60, S.HEALTHY), point(150, S.CRITICAL)])
    assert [(s.start, s.end, s.state) for s in result.component.segments] == [
        (at(0), at(65), S.HEALTHY),
        (at(65), at(150), S.UNKNOWN),
        (at(150), at(155), S.CRITICAL),
        (at(155), at(180), S.UNKNOWN),
    ]


def test_current_rule_watermark_extends_last_record_but_not_beyond_grace() -> None:
    result = history(
        [point(0, S.HEALTHY), point(60, S.HEALTHY)],
        tails=(HistoryTail("rule", at(110), at(0), S.HEALTHY),),
    )
    assert [(s.end, s.state) for s in result.component.segments] == [
        (at(130), S.HEALTHY),
        (at(180), S.UNKNOWN),
    ]


def test_watermark_just_after_the_requested_end_proves_the_preceding_interval() -> None:
    result = history(
        [point(0, S.HEALTHY), point(60, S.HEALTHY)],
        end=100,
        tails=(HistoryTail("rule", at(105), at(0), S.HEALTHY),),
    )
    (segment,) = result.component.segments
    assert segment.end == at(100)
    assert segment.state is S.HEALTHY


def test_reset_cuts_retained_proof_and_does_not_bridge_the_gap() -> None:
    result = history([point(0, S.HEALTHY), point(60, S.CRITICAL)], reset=30, end=100)
    assert [(s.start, s.end, s.state) for s in result.component.segments] == [
        (at(0), at(30), S.HEALTHY),
        (at(30), at(60), S.UNKNOWN),
        (at(60), at(65), S.CRITICAL),
        (at(65), at(100), S.UNKNOWN),
    ]


def test_component_uses_domain_order_before_peak_display_binning() -> None:
    result = history(
        [
            point(0, S.WARNING),
            point(0, S.UNKNOWN, "other"),
            point(60, S.WARNING),
            point(60, S.UNKNOWN, "other"),
        ],
        end=60,
    )
    assert result.component.segments[0].state is S.UNKNOWN
    result = history(
        [
            point(0, S.CRITICAL),
            point(0, S.UNKNOWN, "other"),
            point(60, S.CRITICAL),
            point(60, S.UNKNOWN, "other"),
        ],
        end=60,
    )
    assert result.component.segments[0].state is S.CRITICAL
    assert result.component.segments[0].contains_unknown


def test_single_critical_peak_survives_binning_with_unknown_coverage_flag() -> None:
    result = history([point(0, S.HEALTHY), point(60, S.CRITICAL), point(65, S.HEALTHY)], bins=1)
    (segment,) = result.component.segments
    assert result.component.aggregated
    assert (segment.start, segment.end, segment.state) == (at(0), at(180), S.CRITICAL)
    assert segment.contains_unknown
    assert 61 in segment.evaluation_ids


def test_rule_versions_and_representative_ids_are_preserved_and_bounded() -> None:
    result = history([point(n, S.HEALTHY, version=1 if n < 60 else 2) for n in range(0, 181, 5)])
    (lane,) = result.rules
    assert lane.versions == (1, 2)
    assert len(lane.segments[0].evaluation_ids) == 20
    assert lane.segments[0].state is S.HEALTHY


def test_carry_in_and_carry_out_evaluations_are_clipped_to_window() -> None:
    result = history([point(-20, S.WARNING), point(40, S.HEALTHY), point(100, S.CRITICAL)], end=80)
    assert [(s.start, s.end, s.state) for s in result.component.segments] == [
        (at(0), at(40), S.WARNING),
        (at(40), at(80), S.HEALTHY),
    ]
