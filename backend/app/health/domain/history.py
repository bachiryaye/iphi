"""Recorded state intervals and alarm-preserving display bins (design system §6.3)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

from app.core.observation import SAMPLE_INTERVAL
from app.health.domain.engine import RECORD_EVERY
from app.health.domain.states import HealthState
from app.ingestion.domain.series import TimeWindow

CONTINUITY = RECORD_EVERY + SAMPLE_INTERVAL
MAX_HISTORY_IDS = 20
BAND_PRIORITY = {
    HealthState.HEALTHY: 0,
    HealthState.UNKNOWN: 1,
    HealthState.WARNING: 2,
    HealthState.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    rule_key: str
    version: int
    at: datetime
    state: HealthState
    evaluation_id: int


@dataclass(frozen=True, slots=True)
class HistoryTail:
    rule_key: str
    at: datetime
    since: datetime
    state: HealthState


@dataclass(frozen=True, slots=True)
class HistorySegment:
    start: datetime
    end: datetime
    state: HealthState
    evaluation_ids: tuple[int, ...]
    contains_unknown: bool


@dataclass(frozen=True, slots=True)
class HistoryLane:
    key: str
    versions: tuple[int, ...]
    segments: tuple[HistorySegment, ...]
    aggregated: bool


@dataclass(frozen=True, slots=True)
class HistoryData:
    points: Sequence[HistoryPoint]
    tails: Sequence[HistoryTail]
    rules: Sequence[tuple[str, int]]
    reset_at: datetime | None


@dataclass(frozen=True, slots=True)
class HistoryPolicy:
    window: TimeWindow
    max_segments: int
    tail_grace: timedelta


@dataclass(frozen=True, slots=True)
class StateHistory:
    component: HistoryLane
    rules: tuple[HistoryLane, ...]


def _ids(segments: Sequence[HistorySegment]) -> tuple[int, ...]:
    return tuple(dict.fromkeys(i for segment in segments for i in segment.evaluation_ids))[
        :MAX_HISTORY_IDS
    ]


def _append(result: list[HistorySegment], segment: HistorySegment) -> None:
    if segment.end <= segment.start:
        return
    if (
        result
        and result[-1].end == segment.start
        and (result[-1].state, result[-1].contains_unknown)
        == (segment.state, segment.contains_unknown)
    ):
        prior = result.pop()
        result.append(
            HistorySegment(
                prior.start,
                segment.end,
                segment.state,
                _ids([prior, segment]),
                segment.contains_unknown,
            )
        )
    else:
        result.append(segment)


def _unknown(start: datetime, end: datetime) -> HistorySegment:
    return HistorySegment(start, end, HealthState.UNKNOWN, (), True)


def recorded_segments(
    points: Sequence[HistoryPoint],
    tail: HistoryTail | None,
    reset_at: datetime | None,
    policy: HistoryPolicy,
) -> list[HistorySegment]:
    start, end = policy.window.start, policy.window.end
    # Different immutable rule versions may meet at one instant; the newest version owns it.
    by_time = {
        point.at: point
        for point in sorted(points, key=lambda p: (p.at, p.version, p.evaluation_id))
    }
    ordered = list(by_time.values())
    result: list[HistorySegment] = []
    cursor = start
    for index, point in enumerate(ordered):
        following = ordered[index + 1] if index + 1 < len(ordered) else None
        finish = min(end, following.at) if following else end
        begin = max(start, point.at)
        if begin >= finish:
            continue
        if begin > cursor:
            _append(result, _unknown(cursor, begin))
        valid_until = point.at + SAMPLE_INTERVAL
        if following and following.at - point.at <= CONTINUITY:
            valid_until = following.at
        elif (
            tail
            and tail.state is point.state
            and tail.since <= point.at <= tail.at
            and tail.at - point.at <= CONTINUITY
        ):
            valid_until = tail.at + policy.tail_grace
        if reset_at is not None and point.at < reset_at:
            valid_until = min(valid_until, reset_at)
        known_end = min(finish, max(begin, valid_until))
        _append(
            result,
            HistorySegment(
                begin,
                known_end,
                point.state,
                (point.evaluation_id,),
                point.state is HealthState.UNKNOWN,
            ),
        )
        _append(result, _unknown(known_end, finish))
        cursor = finish
    _append(result, _unknown(cursor, end))
    return result


def component_segments(
    lanes: Sequence[Sequence[HistorySegment]], window: TimeWindow
) -> list[HistorySegment]:
    if not lanes:
        return [_unknown(window.start, window.end)]
    boundaries = sorted(
        {
            window.start,
            window.end,
            *(s.start for row in lanes for s in row),
            *(s.end for row in lanes for s in row),
        }
    )
    positions = [0] * len(lanes)
    result: list[HistorySegment] = []
    for start, end in pairwise(boundaries):
        active = []
        for index, row in enumerate(lanes):
            while positions[index] + 1 < len(row) and row[positions[index]].end <= start:
                positions[index] += 1
            active.append(row[positions[index]])
        state = max((s.state for s in active), key=lambda state: state.severity)
        decisive = [s for s in active if s.state is state]
        _append(
            result,
            HistorySegment(
                start, end, state, _ids(decisive), any(s.contains_unknown for s in active)
            ),
        )
    return result


def display_bins(
    segments: Sequence[HistorySegment], policy: HistoryPolicy
) -> tuple[tuple[HistorySegment, ...], bool]:
    if len(segments) <= policy.max_segments:
        return tuple(segments), False
    width = (policy.window.end - policy.window.start) / policy.max_segments
    result: list[HistorySegment] = []
    index = 0
    for bucket in range(policy.max_segments):
        start = policy.window.start + width * bucket
        end = policy.window.end if bucket + 1 == policy.max_segments else start + width
        while index + 1 < len(segments) and segments[index].end <= start:
            index += 1
        candidates = []
        scan = index
        while scan < len(segments) and segments[scan].start < end:
            if segments[scan].end > start:
                candidates.append(segments[scan])
            scan += 1
        state = max((s.state for s in candidates), key=BAND_PRIORITY.__getitem__)
        decisive = [s for s in candidates if s.state is state]
        _append(
            result,
            HistorySegment(
                start, end, state, _ids(decisive), any(s.contains_unknown for s in candidates)
            ),
        )
    return tuple(result), True


def state_history(data: HistoryData, policy: HistoryPolicy) -> StateHistory:
    tails = {tail.rule_key: tail for tail in data.tails}
    keys = sorted({key for key, _ in data.rules} | {point.rule_key for point in data.points})
    raw = []
    rows = []
    for key in keys:
        points = [point for point in data.points if point.rule_key == key]
        segments = recorded_segments(points, tails.get(key), data.reset_at, policy)
        raw.append(segments)
        displayed, binned = display_bins(segments, policy)
        versions = tuple(
            sorted(
                {version for name, version in data.rules if name == key}
                | {point.version for point in points}
            )
        )
        rows.append(HistoryLane(key, versions, displayed, binned))
    component, binned = display_bins(component_segments(raw, policy.window), policy)
    return StateHistory(HistoryLane("component", (), component, binned), tuple(rows))
