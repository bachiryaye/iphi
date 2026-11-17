"""Measures the performance targets of architecture §07.2 against a running stack.

    docker compose exec api python -m scripts.perf [--history-days 7]

`--history-days` writes simulated samples to the database: disposable stack only.
"""

import argparse
import math
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import create_db_engine, create_session_factory
from app.core.observation import SAMPLE_INTERVAL, ObservationSource, tick_of
from app.core.settings import Settings
from app.ingestion.domain.collection import CollectionOutcome
from app.ingestion.domain.series import MAX_POINTS
from app.ingestion.domain.validation import AcceptedSample
from app.ingestion.repository import CollectionRunRepository, ObservationRepository
from app.simulation.domain.generator import MAX_TICKS_PER_BATCH, generate_range
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.domain.runs import ScenarioRun, baseline_plan
from scripts.client import DEFAULT_BASE_URL, Api, Json, ToolError, wait_until

BACKFILL_CONNECTOR = "perf-backfill"
TICKS_PER_DAY = timedelta(days=1) // SAMPLE_INTERVAL
WARMUP_REQUESTS = 5
DETECTION_POLL_S = 0.2

# Targets of architecture §07.2.
API_P95_TARGET_MS = 300.0
CYCLE_P95_TARGET_MS = 500.0
DETECTION_TARGET_S = 15.0


@dataclass(frozen=True, slots=True)
class Measure:
    indicator: str
    observed: str
    target: str
    met: bool


def percentile(values: list[float], share: float) -> float:
    """Nearest-rank percentile: an observed value, never an interpolation."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(share * len(ordered)) - 1)]


def summary(values: list[float], unit: str) -> str:
    return (
        f"p50 {statistics.median(values):.0f} {unit}, p95 {percentile(values, 0.95):.0f} {unit}, "
        f"max {max(values):.0f} {unit} (n = {len(values)})"
    )


def backfill(
    engine: Engine,
    session_factory: sessionmaker[Session],
    ids: dict[str, uuid.UUID],
    days: float,
    seed: int,
) -> int:
    # Evidence samples outlive a reset (ADR 0008): anchoring on them would leave a gap before
    # the current history.
    with session_factory() as session:
        oldest = session.execute(
            text(
                "SELECT min(observed_at) FROM metric_sample WHERE observed_at >= ("
                "SELECT started_at FROM scenario_run"
                " WHERE scenario_key = 'baseline' AND status = 'active')"
            )
        ).scalar_one()
    if oldest is None:
        raise ToolError("no stored sample yet: let the worker run a cycle before the backfill")
    last = tick_of(oldest) - 1
    first = last - round(days * TICKS_PER_DAY) + 1
    start = datetime.now(UTC) - timedelta(days=days + 1)
    baseline = ScenarioRun.from_plan(
        baseline_plan(start, seed, BACKFILL_CONNECTOR), uuid.uuid4(), 0
    )
    stored = 0
    began = time.monotonic()
    for batch_first in range(first, last + 1, MAX_TICKS_PER_BATCH):
        batch_last = min(last, batch_first + MAX_TICKS_PER_BATCH - 1)
        ticks = generate_range(SIMULATED_PLATFORM, [baseline], batch_first, batch_last)
        samples = [
            AcceptedSample(
                ids[s.component_key],
                s.metric.value,
                s.value,
                s.unit,
                s.quality,
                s.observed_at,
                None,
            )
            for tick in ticks
            for s in tick.samples
        ]
        with session_factory.begin() as session:
            now = datetime.now(UTC)
            runs = CollectionRunRepository(session)
            run_id = runs.open(BACKFILL_CONNECTOR, ObservationSource.SIMULATION, now)
            count = ObservationRepository(session).insert_samples(
                samples, ObservationSource.SIMULATION, run_id, now
            )
            runs.record(run_id, CollectionOutcome(sample_count=count, log_count=0), now)
        stored += count
        done = (batch_last - first + 1) / (last - first + 1)
        print(f"\r  backfill {done:5.1%}  {stored:,} samples", end="", file=sys.stderr)
    print(f"  in {time.monotonic() - began:.0f} s", file=sys.stderr)
    # Steady state, as autovacuum leaves it soon after a bulk load.
    began = time.monotonic()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("VACUUM (ANALYZE) metric_sample"))
    print(f"  vacuum and analyze in {time.monotonic() - began:.0f} s", file=sys.stderr)
    return stored


def api_latency(api: Api, component_id: str, requests: int) -> list[Measure]:
    span = api.get(
        "/metrics", component_id=component_id, metric_name="probe_latency_ms", max_points=1
    )
    now = datetime.fromisoformat(span["window_end"])

    def series(window: timedelta) -> dict[str, str | int | list[str]]:
        return {
            "component_id": component_id,
            "metric_name": "probe_latency_ms",
            "max_points": MAX_POINTS,
            "from": (now - window).isoformat(),
            "to": now.isoformat(),
        }

    raw_window = SAMPLE_INTERVAL * MAX_POINTS
    raw_hours = raw_window.total_seconds() / 3600
    targets: list[tuple[str, str, dict[str, str | int | list[str]]]] = [
        ("GET /incidents (50 newest)", "/incidents", {"limit": 50}),
        (
            f"GET /metrics, last {raw_hours:.1f} h ({MAX_POINTS} raw points)",
            "/metrics",
            series(raw_window),
        ),
        (
            f"GET /metrics, last 7 days ({MAX_POINTS} buckets)",
            "/metrics",
            series(timedelta(days=7)),
        ),
    ]
    measures = []
    for label, path, query in targets:
        for _ in range(WARMUP_REQUESTS):
            api.timed_get(path, **query)
        replies = [api.timed_get(path, **query) for _ in range(requests)]
        durations = [reply.elapsed_ms for reply in replies]
        returned = ""
        if path == "/metrics":
            last = replies[-1].body
            returned = (
                f"; {len(last['points']) + len(last['buckets'])} {last['mode']} points returned"
            )
        measures.append(
            Measure(
                label,
                summary(durations, "ms") + returned,
                f"p95 < {API_P95_TARGET_MS:.0f} ms",
                percentile(durations, 0.95) < API_P95_TARGET_MS,
            )
        )
    return measures


def cycle_duration(api: Api, cycles: int) -> Measure:
    durations: list[float] = []
    seen: str | None = None
    interval_s = float(api.get("/system/status")["cycle_interval_s"])
    deadline = time.monotonic() + cycles * interval_s * 3 + 60
    while len(durations) < cycles:
        heartbeat = api.get("/system/status")["worker"]["heartbeat"]
        if heartbeat is not None and heartbeat["last_cycle_at"] != seen:
            seen = heartbeat["last_cycle_at"]
            durations.append(float(heartbeat["last_cycle_duration_ms"]))
        if time.monotonic() > deadline:
            raise ToolError(f"only {len(durations)} worker cycles observed, {cycles} expected")
        time.sleep(1.0)
    p95 = percentile(durations, 0.95)
    return Measure(
        "Worker cycle duration (realtime clock)",
        summary(durations, "ms"),
        f"p95 < {CYCLE_P95_TARGET_MS:.0f} ms",
        p95 < CYCLE_P95_TARGET_MS,
    )


def _settled(api: Api) -> Json | None:
    health: Json = api.platform()["health"]
    return health if health["state"] == "healthy" and not api.active_incidents() else None


def detection_delay(api: Api, collector_id: str, runs: int) -> Measure:

    def critical() -> bool | None:
        return api.component(collector_id)["health"]["state"] == "critical" or None

    delays = []
    for _ in range(runs):
        api.set_clock("realtime")
        wait_until("platform Healthy without active incident", lambda: _settled(api), 120)
        began = time.monotonic()
        run = api.start_scenario("collector_down")
        wait_until("collector-01 Critical after collector_down", critical, 60, DETECTION_POLL_S)
        delays.append(time.monotonic() - began)
        api.stop_run(run["id"])
        # Shortens the 300 s connectivity window before the next injection.
        api.set_clock("accelerated", 60)
        wait_until("recovery after collector_down", lambda: _settled(api), 120)
    api.set_clock("realtime")
    listed = ", ".join(f"{delay:.1f} s" for delay in delays)
    return Measure(
        "Detection delay, collector_down (realtime clock)",
        f"{listed} (max {max(delays):.1f} s)",
        f"<= {DETECTION_TARGET_S:.0f} s (3 cycles)",
        max(delays) <= DETECTION_TARGET_S,
    )


def stored_volume(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as session:
        count, oldest, newest, size = session.execute(
            text(
                "SELECT count(*), min(observed_at), max(observed_at), "
                "pg_size_pretty(pg_total_relation_size('metric_sample')) FROM metric_sample"
            )
        ).one()
    days = 0.0 if oldest is None else (newest - oldest).total_seconds() / 86_400
    return f"{count:,} samples over {days:.1f} days, table and indexes {size}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Measure the IPHI performance targets.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API root, without /api/v1.")
    parser.add_argument("--requests", type=int, default=200, help="Requests per API measure.")
    parser.add_argument("--cycles", type=int, default=36, help="Worker cycles to observe.")
    parser.add_argument("--detections", type=int, default=3, help="collector_down injections.")
    parser.add_argument(
        "--history-days",
        type=float,
        default=0.0,
        help="Store this many days of baseline samples first (disposable stack only).",
    )
    arguments = parser.parse_args(argv)
    settings = Settings()
    if not 0 <= arguments.history_days <= settings.retention_days:
        parser.error(f"--history-days must be 0..{settings.retention_days} (retention)")
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        api = Api(arguments.base_url)
        if api.readiness() is None:
            raise ToolError("the stack is not ready (GET /ready)")
        ids = {key: item["id"] for key, item in api.components().items()}
        if arguments.history_days > 0:
            components = {key: uuid.UUID(value) for key, value in ids.items()}
            backfill(engine, session_factory, components, arguments.history_days, settings.sim_seed)
        measures = [
            *api_latency(api, ids["historian-01"], arguments.requests),
            cycle_duration(api, arguments.cycles),
            detection_delay(api, ids["collector-01"], arguments.detections),
        ]
    except ToolError as failure:
        print(f"PERF FAILED: {failure}", file=sys.stderr)
        return 1
    print(f"Stored history: {stored_volume(session_factory)}\n")
    print("| Indicator | Observed | Target | Met |")
    print("|---|---|---|---|")
    for measure in measures:
        print(
            f"| {measure.indicator} | {measure.observed} | {measure.target} | "
            f"{'yes' if measure.met else 'NO'} |"
        )
    return 0 if all(measure.met for measure in measures) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
