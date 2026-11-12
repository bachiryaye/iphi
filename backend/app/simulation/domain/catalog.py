"""Scenario catalog (architecture §05.6): definitions, bounded parameters and fault effects.

Effects are pure functions of the nominal reading and the run context (rules.md P-02, P-07).
They never read health-rule thresholds: the expected outcomes document what the default rules
should conclude, they do not drive the signal.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from app.simulation.domain.signals import (
    LogLine,
    LogSeverity,
    Metric,
    Reading,
    draw,
    jitter,
    lerp,
)
from app.topology.domain import ComponentType

# Buffer size of the simulated gateways and collectors; a growing backlog saturates there.
QUEUE_CAPACITY = 100_000
MAX_ERROR_LOGS_PER_SAMPLE = 3
PEAK_JITTER = 0.03


class ScenarioKey(StrEnum):
    BASELINE = "baseline"
    COLLECTOR_DOWN = "collector_down"
    LATENCY_RISE = "latency_rise"
    STALE_DATA = "stale_data"
    INTERMITTENT_LOSS = "intermittent_loss"
    ERROR_BURST = "error_burst"
    RESOURCE_PRESSURE = "resource_pressure"
    BACKLOG_GROWTH = "backlog_growth"
    TELEMETRY_BLACKOUT = "telemetry_blackout"


class ScenarioKind(StrEnum):
    BASELINE = "baseline"
    FAULT = "fault"


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: str
    unit: str
    default: float
    minimum: float
    maximum: float
    description: str


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    signal: str
    state: str
    incident: str


@dataclass(frozen=True, slots=True)
class EffectContext:
    """Inputs of a fault effect at one sample slot of one component."""

    seed: int
    scenario: ScenarioKey
    component_key: str
    tick: int
    run_tick: int
    elapsed_s: float
    parameters: Mapping[str, float]

    def draw(self, *parts: str | int) -> float:
        return draw(self.seed, self.scenario, self.component_key, self.tick, *parts)

    def progress(self, ramp_parameter: str) -> float:
        return min(1.0, self.elapsed_s / self.parameters[ramp_parameter])


Effect = Callable[[Reading, EffectContext], Reading | None]
"""Returns the faulty reading, or None when the connector observes nothing at all."""


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    key: ScenarioKey
    title: str
    description: str
    kind: ScenarioKind
    default_target: str | None
    eligible_types: frozenset[ComponentType]
    parameters: tuple[ParameterSpec, ...]
    expected: ExpectedOutcome
    effect: Effect | None
    stops_data_flow: bool = False


def _outage(_reading: Reading, _ctx: EffectContext) -> Reading:
    return Reading.unanswered()


def _blackout(_reading: Reading, _ctx: EffectContext) -> None:
    return None


def _latency_rise(reading: Reading, ctx: EffectContext) -> Reading:
    base = reading.values[Metric.PROBE_LATENCY_MS]
    peak = jitter(ctx.parameters["peak_ms"], PEAK_JITTER, ctx.draw("peak"))
    value = lerp(base, peak, ctx.progress("ramp_s"))
    return reading.with_value(Metric.PROBE_LATENCY_MS, round(value, 1))


def _stale_data(reading: Reading, ctx: EffectContext) -> Reading:
    # The service still answers but its process data stopped updating: age grows 1 s per s.
    base = reading.values[Metric.DATA_AGE_S]
    return reading.with_value(Metric.DATA_AGE_S, round(base + ctx.elapsed_s, 1))


def _intermittent_loss(reading: Reading, ctx: EffectContext) -> Reading:
    # Drops only on odd slots, so two consecutive probes never both fail: the pattern stays a
    # connectivity problem (ratio over a window), not a sustained outage.
    ratio = ctx.parameters["loss_ratio"]
    dropped = ctx.run_tick % 2 == 1 and ctx.draw("drop") < 2 * ratio
    return Reading.unanswered() if dropped else reading


def _error_burst(reading: Reading, ctx: EffectContext) -> Reading:
    count = max(1, round(jitter(ctx.parameters["errors_per_sample"], 0.3, ctx.draw("count"))))
    logs = tuple(
        LogLine(
            LogSeverity.ERROR,
            "Upstream request failed: read timeout",
            MappingProxyType({"request_id": f"{math.floor(ctx.draw('request', i) * 16**8):08x}"}),
        )
        for i in range(min(count, MAX_ERROR_LOGS_PER_SAMPLE))
    )
    return reading.with_value(Metric.ERROR_COUNT, count).with_logs(logs)


def _resource_pressure(reading: Reading, ctx: EffectContext) -> Reading:
    progress = ctx.progress("ramp_s")
    for metric in (Metric.CPU_PCT, Metric.MEM_PCT):
        peak = jitter(ctx.parameters["peak_pct"], PEAK_JITTER / 3, ctx.draw("peak", metric))
        value = min(100.0, lerp(reading.values[metric], peak, progress))
        reading = reading.with_value(metric, round(value, 1))
    return reading


def _backlog_growth(reading: Reading, ctx: EffectContext) -> Reading:
    base = reading.values[Metric.QUEUE_DEPTH]
    value = min(QUEUE_CAPACITY, base + ctx.parameters["growth_per_s"] * ctx.elapsed_s)
    return reading.with_value(Metric.QUEUE_DEPTH, round(value))


_SERVICES = frozenset(ComponentType) - {ComponentType.SOURCE}
_RAMP = "Time to reach the peak."

CATALOG: tuple[ScenarioDefinition, ...] = (
    ScenarioDefinition(
        key=ScenarioKey.BASELINE,
        title="Baseline",
        description="Nominal values with bounded noise on every component. Always running; "
        "fault scenarios are layered on top of it.",
        kind=ScenarioKind.BASELINE,
        default_target=None,
        eligible_types=frozenset(),
        parameters=(),
        expected=ExpectedOutcome(
            signal="Nominal noisy values on all components.",
            state="All components Healthy.",
            incident="None.",
        ),
        effect=None,
    ),
    ScenarioDefinition(
        key=ScenarioKey.COLLECTOR_DOWN,
        title="Collector down",
        description="The collector stops answering its probe and stops logging; downstream "
        "process data stops updating.",
        kind=ScenarioKind.FAULT,
        default_target="collector-01",
        eligible_types=frozenset({ComponentType.COLLECTOR}),
        parameters=(),
        expected=ExpectedOutcome(
            signal="up = 0, no other metric and no application log from the target; "
            "data_age_s grows on historian-01 and analytics-01.",
            state="Target Critical; historian-01, data-api-01 and analytics-01 impacted; "
            "platform Critical.",
            incident="One availability incident on the target; downstream suppressed as impact.",
        ),
        effect=_outage,
        stops_data_flow=True,
    ),
    ScenarioDefinition(
        key=ScenarioKey.LATENCY_RISE,
        title="Latency rise",
        description="Probe latency ramps linearly from nominal to the peak, then holds.",
        kind=ScenarioKind.FAULT,
        default_target="edge-gateway-01",
        eligible_types=_SERVICES,
        parameters=(
            ParameterSpec(
                "peak_ms", "ms", 1500, 300, 5000, "Latency reached at the end of the ramp."
            ),
            ParameterSpec("ramp_s", "s", 300, 30, 1800, _RAMP),
        ),
        expected=ExpectedOutcome(
            signal="probe_latency_ms from nominal (≈ 50 ms) to 1 500 ms in 5 min.",
            state="Warning, then Critical; stable return to Healthy after stop.",
            incident="One latency incident, severity raised, auto-resolved after stop.",
        ),
        effect=_latency_rise,
    ),
    ScenarioDefinition(
        key=ScenarioKey.STALE_DATA,
        title="Stale data",
        description="The service keeps answering but its process data stops updating. "
        "Simplification: the age is not propagated to downstream components.",
        kind=ScenarioKind.FAULT,
        default_target="historian-01",
        eligible_types=frozenset({ComponentType.HISTORIAN, ComponentType.ANALYTICS}),
        parameters=(),
        expected=ExpectedOutcome(
            signal="up = 1, data_age_s grows by 1 s per second.",
            state="Target Warning, then Critical.",
            incident="One freshness incident, distinct from availability; no availability "
            "incident.",
        ),
        effect=_stale_data,
    ),
    ScenarioDefinition(
        key=ScenarioKey.INTERMITTENT_LOSS,
        title="Intermittent loss",
        description="Isolated probe failures: never two in a row, at the requested ratio.",
        kind=ScenarioKind.FAULT,
        default_target="edge-gateway-01",
        eligible_types=frozenset(
            {ComponentType.SOURCE, ComponentType.GATEWAY, ComponentType.COLLECTOR}
        ),
        parameters=(
            ParameterSpec("loss_ratio", "ratio", 0.3, 0.05, 0.5, "Share of failed probes."),
        ),
        expected=ExpectedOutcome(
            signal="up alternates 0/1 (≈ 30 % failed probes, isolated).",
            state="Warning, then Critical through R-CONN-001, without state oscillation.",
            incident="One connectivity incident, not one per drop.",
        ),
        effect=_intermittent_loss,
    ),
    ScenarioDefinition(
        key=ScenarioKey.ERROR_BURST,
        title="Error burst",
        description="Sustained request errors with repeated error logs sharing one message.",
        kind=ScenarioKind.FAULT,
        default_target="data-api-01",
        eligible_types=_SERVICES,
        parameters=(
            ParameterSpec("errors_per_sample", "count", 6, 2, 50, "Mean errors per 5 s sample."),
        ),
        expected=ExpectedOutcome(
            signal="error_count high on every sample; repeated error logs, same fingerprint.",
            state="Warning, then Critical.",
            incident="One errors incident with a growing occurrence count.",
        ),
        effect=_error_burst,
    ),
    ScenarioDefinition(
        key=ScenarioKey.RESOURCE_PRESSURE,
        title="Resource pressure",
        description="CPU and memory usage ramp to the peak, then hold.",
        kind=ScenarioKind.FAULT,
        default_target="timeseries-db-01",
        eligible_types=_SERVICES,
        parameters=(
            ParameterSpec("peak_pct", "%", 97, 86, 99.5, "CPU and memory usage at the peak."),
            ParameterSpec("ramp_s", "s", 180, 30, 1800, _RAMP),
        ),
        expected=ExpectedOutcome(
            signal="cpu_pct and mem_pct above 90 %.",
            state="Warning, then Critical.",
            incident="One resources incident.",
        ),
        effect=_resource_pressure,
    ),
    ScenarioDefinition(
        key=ScenarioKey.BACKLOG_GROWTH,
        title="Backlog growth",
        description="The internal queue grows linearly up to the buffer capacity.",
        kind=ScenarioKind.FAULT,
        default_target="collector-01",
        eligible_types=frozenset({ComponentType.GATEWAY, ComponentType.COLLECTOR}),
        parameters=(
            ParameterSpec("growth_per_s", "count/s", 20, 1, 200, "Queued items added per second."),
        ),
        expected=ExpectedOutcome(
            signal="queue_depth grows steadily.",
            state="Warning, then Critical.",
            incident="One backlog incident.",
        ),
        effect=_backlog_growth,
    ),
    ScenarioDefinition(
        key=ScenarioKey.TELEMETRY_BLACKOUT,
        title="Telemetry blackout",
        description="The connector observes nothing for the target: no probe result, no "
        "metric, no log. The component itself keeps running.",
        kind=ScenarioKind.FAULT,
        default_target="historian-01",
        eligible_types=frozenset(ComponentType),
        parameters=(),
        expected=ExpectedOutcome(
            signal="No observation at all for the target.",
            state="Target Unknown, never Healthy.",
            incident="One telemetry_loss incident.",
        ),
        effect=_blackout,
    ),
)

SCENARIOS: Mapping[ScenarioKey, ScenarioDefinition] = MappingProxyType(
    {definition.key: definition for definition in CATALOG}
)
