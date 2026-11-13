"""Pure observation generator: f(seed, component, metric, tick, runs covering the tick).

No hidden state (ADR 0002): a tick can be generated in any order, after any restart, and yields
the same observations. Inputs are component keys and scenario keys, never database IDs, so two
clean environments with the same seed and run times produce the same fingerprint.
"""

import functools
import hashlib
import json
import math
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from app.core.observation import LogSeverity, ObservationSource, Quality, tick_of, tick_time
from app.simulation.domain.catalog import SCENARIOS, EffectContext, ScenarioKey
from app.simulation.domain.errors import SimulationNotInitializedError
from app.simulation.domain.platform import SimulatedComponent, SimulatedPlatform
from app.simulation.domain.runs import ScenarioRun
from app.simulation.domain.signals import (
    OBSERVATION_SOURCE,
    UNITS,
    LogLine,
    Metric,
    Reading,
    draw,
    jitter,
)

LATENCY_JITTER = 0.2
LOAD_JITTER = 0.1
QUEUE_JITTER = 0.3
DATA_AGE_JITTER = 0.3
# At most one nominal error per block of 12 samples (60 s): any 60 s window then holds two at
# most, far below R-ERR-001's raise threshold, whatever the seed.
ERROR_BLOCK_SAMPLES = 12
NOMINAL_ERROR_BLOCK_PROBABILITY = 0.25
INFO_LOG_EVERY_SAMPLES = 12
# One hour of 5 s samples: bounds a single generation call (C-07).
MAX_TICKS_PER_BATCH = 720
_METRIC_ORDER = tuple(Metric)


@dataclass(frozen=True, slots=True)
class GeneratedSample:
    component_key: str
    metric: Metric
    value: float
    unit: str
    observed_at: datetime
    quality: Quality
    scenario_run_id: uuid.UUID
    scenario_key: ScenarioKey
    source: ObservationSource = OBSERVATION_SOURCE


@dataclass(frozen=True, slots=True)
class GeneratedLog:
    component_key: str
    severity: LogSeverity
    message: str
    attributes: Mapping[str, str | int]
    observed_at: datetime
    scenario_run_id: uuid.UUID
    scenario_key: ScenarioKey
    source: ObservationSource = OBSERVATION_SOURCE


@dataclass(frozen=True, slots=True)
class TickObservations:
    tick: int
    observed_at: datetime
    samples: tuple[GeneratedSample, ...]
    logs: tuple[GeneratedLog, ...]


def _nominal_reading(seed: int, component: SimulatedComponent, tick: int) -> Reading:
    profile, key = component.profile, component.key

    def noisy(metric: Metric, base: float, relative: float) -> float:
        return jitter(base, relative, draw(seed, key, metric, tick))

    values: dict[Metric, float] = {
        Metric.PROBE_LATENCY_MS: round(
            noisy(Metric.PROBE_LATENCY_MS, profile.latency_ms, LATENCY_JITTER), 1
        ),
        Metric.CPU_PCT: round(noisy(Metric.CPU_PCT, profile.cpu_pct, LOAD_JITTER), 1),
        Metric.MEM_PCT: round(noisy(Metric.MEM_PCT, profile.mem_pct, LOAD_JITTER), 1),
        Metric.ERROR_COUNT: float(_nominal_error(seed, key, tick)),
    }
    if profile.queue_depth is not None:
        values[Metric.QUEUE_DEPTH] = round(
            noisy(Metric.QUEUE_DEPTH, profile.queue_depth, QUEUE_JITTER)
        )
    if profile.data_age_s is not None:
        values[Metric.DATA_AGE_S] = round(
            noisy(Metric.DATA_AGE_S, profile.data_age_s, DATA_AGE_JITTER), 1
        )

    logs: list[LogLine] = []
    if (tick + _log_phase(seed, key)) % INFO_LOG_EVERY_SAMPLES == 0:
        logs.append(
            LogLine(
                LogSeverity.INFO, "Processing cycle completed", MappingProxyType({"cycle": tick})
            )
        )
    if values[Metric.ERROR_COUNT]:
        logs.append(
            LogLine(LogSeverity.WARNING, "Transient request error; retried", MappingProxyType({}))
        )
    return Reading(up=True, values=MappingProxyType(values), logs=tuple(logs))


def _nominal_error(seed: int, key: str, tick: int) -> bool:
    block, slot = divmod(tick, ERROR_BLOCK_SAMPLES)
    return slot == _error_slot(seed, key, block)


# Pure functions of their arguments, memoized: a batch recomputes them for every tick otherwise.
@functools.lru_cache(maxsize=1024)
def _log_phase(seed: int, key: str) -> int:
    return math.floor(draw(seed, key, "log-phase") * INFO_LOG_EVERY_SAMPLES)


@functools.lru_cache(maxsize=4096)
def _error_slot(seed: int, key: str, block: int) -> int | None:
    """Slot of the block's single nominal error, or None for an error-free block."""
    if draw(seed, key, "error-block", block) >= NOMINAL_ERROR_BLOCK_PROBABILITY:
        return None
    return math.floor(draw(seed, key, "error-slot", block) * ERROR_BLOCK_SAMPLES)


@dataclass(frozen=True, slots=True)
class _TickContext:
    tick: int
    at: datetime
    baseline: ScenarioRun
    faults: Mapping[str, ScenarioRun]
    outages: Mapping[str, ScenarioRun]


def generate_tick(
    platform: SimulatedPlatform, runs: Sequence[ScenarioRun], tick: int
) -> TickObservations:
    at = tick_time(tick)
    covering = [run for run in runs if run.covers(at)]
    baseline = next((r for r in covering if r.scenario is ScenarioKey.BASELINE), None)
    if baseline is None:
        raise SimulationNotInitializedError(
            f"No baseline run covers {at.isoformat()}; reset the simulation."
        )
    faults = {r.target_key: r for r in covering if r.target_key is not None}
    context = _TickContext(tick, at, baseline, faults, _upstream_outages(platform, faults.values()))

    samples: list[GeneratedSample] = []
    logs: list[GeneratedLog] = []
    for component in platform.components:
        observed = _observe(component, context)
        if observed is None:
            continue
        reading, run = observed
        samples.extend(_samples(component.key, reading, at, run))
        logs.extend(
            GeneratedLog(
                component.key,
                line.severity,
                line.message,
                line.attributes,
                at,
                run.id,
                run.scenario,
            )
            for line in reading.logs
        )
    return TickObservations(tick, at, tuple(samples), tuple(logs))


def _observe(
    component: SimulatedComponent, context: _TickContext
) -> tuple[Reading, ScenarioRun] | None:
    """The component's reading and the run that shaped it, or None when nothing is observed."""
    nominal = _nominal_reading(context.baseline.seed, component, context.tick)
    own = context.faults.get(component.key)
    reading = nominal if own is None else _apply_fault(own, nominal, component.key, context)
    if reading is None:
        return None
    upstream = context.outages.get(component.key)
    if upstream is None or not reading.up or Metric.DATA_AGE_S not in reading.values:
        return reading, own or context.baseline
    # Data stopped flowing at the upstream outage: downstream data ages from then on.
    age = reading.values[Metric.DATA_AGE_S] + (context.at - upstream.started_at).total_seconds()
    return reading.with_value(Metric.DATA_AGE_S, round(age, 1)), own or upstream


def generate_range(
    platform: SimulatedPlatform, runs: Sequence[ScenarioRun], first_tick: int, last_tick: int
) -> list[TickObservations]:
    """Ticks `first_tick` to `last_tick` inclusive."""
    return [generate_tick(platform, runs, tick) for tick in range(first_tick, last_tick + 1)]


def fingerprint(ticks: Iterable[TickObservations]) -> str:
    """SHA-256 of a canonical serialization; run IDs excluded, scenario keys included."""
    digest = hashlib.sha256()
    for observations in sorted(ticks, key=lambda t: t.tick):
        for sample in observations.samples:
            digest.update(
                _canonical(
                    "sample",
                    sample.observed_at,
                    sample.component_key,
                    sample.metric,
                    sample.value,
                    sample.unit,
                    sample.quality,
                    sample.scenario_key,
                    sample.source,
                )
            )
        for log in observations.logs:
            digest.update(
                _canonical(
                    "log",
                    log.observed_at,
                    log.component_key,
                    log.severity,
                    log.message,
                    dict(log.attributes),
                    log.scenario_key,
                    log.source,
                )
            )
    return digest.hexdigest()


def _canonical(*fields: object) -> bytes:
    rendered = [f.isoformat() if isinstance(f, datetime) else f for f in fields]
    return json.dumps(rendered, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _apply_fault(
    run: ScenarioRun, reading: Reading, component_key: str, context: _TickContext
) -> Reading | None:
    effect = SCENARIOS[run.scenario].effect
    if effect is None:
        return reading
    effect_context = EffectContext(
        seed=run.seed,
        scenario=run.scenario,
        component_key=component_key,
        tick=context.tick,
        run_tick=context.tick - tick_of(run.started_at),
        elapsed_s=(context.at - run.started_at).total_seconds(),
        parameters=run.parameters,
    )
    return effect(reading, effect_context)


def _upstream_outages(
    platform: SimulatedPlatform, faults: Iterable[ScenarioRun]
) -> dict[str, ScenarioRun]:
    """Earliest active outage upstream of each component, for runs that stop the data flow."""
    affected: dict[str, ScenarioRun] = {}
    for run in sorted(faults, key=lambda r: r.started_at):
        if run.target_key is None or not SCENARIOS[run.scenario].stops_data_flow:
            continue
        for key in platform.downstream(run.target_key):
            affected.setdefault(key, run)
    return affected


def _samples(
    component_key: str, reading: Reading, at: datetime, run: ScenarioRun
) -> list[GeneratedSample]:
    measured = [(Metric.UP, 1.0 if reading.up else 0.0)]
    measured += [
        (metric, reading.values[metric]) for metric in _METRIC_ORDER if metric in reading.values
    ]
    return [
        # float() keeps counts and gauges in one representation for the canonical fingerprint.
        GeneratedSample(
            component_key,
            metric,
            float(value),
            UNITS[metric],
            at,
            Quality.GOOD,
            run.id,
            run.scenario,
        )
        for metric, value in measured
    ]
