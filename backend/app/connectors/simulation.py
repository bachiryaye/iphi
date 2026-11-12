"""Simulation connector: reads the pure generator through the simulation service (ADR 0014)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.connectors.domain import (
    CollectionRequest,
    CollectionResult,
    ConnectorIssue,
    ObservedLog,
    ObservedSample,
)
from app.core.observation import ObservationSource
from app.simulation.domain.clock import first_tick_at_or_after, tick_of, tick_time
from app.simulation.domain.generator import MAX_TICKS_PER_BATCH, TickObservations

SIMULATION_CONNECTOR_KEY = "simulation"


class SimulatedSource(Protocol):
    def coverage_start(self) -> datetime: ...

    def observations(self, first_tick: int, last_tick: int) -> list[TickObservations]: ...


class SimulationConnector:
    """Collects every elapsed sample slot once, so accelerated time yields dense series.

    The first slot is the latest of: the one after the watermark, the oldest slot ingestion
    still accepts, and the first slot of the active baseline. The last bound keeps a reset from
    replaying ticks of the runs it just stopped into the freshly purged history.
    """

    key = SIMULATION_CONNECTOR_KEY
    source = ObservationSource.SIMULATION

    def __init__(self, simulation: SimulatedSource) -> None:
        self._simulation = simulation

    def collect(self, request: CollectionRequest) -> CollectionResult:
        last = tick_of(request.now)
        oldest_accepted = max(
            first_tick_at_or_after(request.not_before),
            last - MAX_TICKS_PER_BATCH + 1,
        )
        coverage = first_tick_at_or_after(self._simulation.coverage_start())
        first = max(oldest_accepted, coverage)
        issues: tuple[ConnectorIssue, ...] = ()
        if request.resume_after is not None:
            resume = max(tick_of(request.resume_after) + 1, coverage)
            if resume < oldest_accepted:
                skipped = oldest_accepted - resume
                issues = (_skipped(skipped, tick_time(resume), tick_time(oldest_accepted)),)
            first = max(first, resume)
        if first > last:
            return CollectionResult(watermark=request.resume_after)
        ticks = self._simulation.observations(first, last)
        return CollectionResult(
            samples=tuple(_samples(ticks)),
            logs=tuple(_logs(ticks)),
            issues=issues,
            watermark=tick_time(last),
        )


def _skipped(slots: int, start: datetime, end: datetime) -> ConnectorIssue:
    """Slots older than ingestion accepts are never generated; saying so keeps the loss visible."""
    return ConnectorIssue(
        "SAMPLE_SLOTS_SKIPPED",
        f"{slots} sample slot(s) from {start.isoformat()} to {end.isoformat()} were older "
        "than the late tolerance and were not collected.",
    )


def _samples(ticks: Sequence[TickObservations]) -> list[ObservedSample]:
    return [
        ObservedSample(
            s.component_key,
            s.metric.value,
            s.value,
            s.unit,
            s.quality,
            s.observed_at,
            s.scenario_run_id,
        )
        for tick in ticks
        for s in tick.samples
    ]


def _logs(ticks: Sequence[TickObservations]) -> list[ObservedLog]:
    return [
        ObservedLog(
            log.component_key,
            log.severity,
            log.message,
            dict(log.attributes),
            log.observed_at,
            log.scenario_run_id,
        )
        for tick in ticks
        for log in tick.logs
    ]
