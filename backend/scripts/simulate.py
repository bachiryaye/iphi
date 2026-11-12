"""Preview simulated observations without a database, and print their fingerprint.

    uv run python -m scripts.simulate collector_down --ticks 120
    uv run python -m scripts.simulate latency_rise --param peak_ms=2000 --format jsonl

Running it twice with the same arguments prints the same fingerprint (ADR 0002).
"""

import argparse
import json
import sys
import uuid
from collections import Counter
from datetime import datetime

from app.core.exceptions import IphiError
from app.core.settings import MAX_SEED
from app.simulation.domain.catalog import SCENARIOS, ScenarioKey
from app.simulation.domain.clock import first_tick_at_or_after
from app.simulation.domain.generator import (
    MAX_TICKS_PER_BATCH as MAX_TICKS,
)
from app.simulation.domain.generator import (
    TickObservations,
    fingerprint,
    generate_range,
)
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.domain.runs import (
    RunPlan,
    ScenarioRun,
    StartRequest,
    baseline_plan,
    plan_run,
)
from app.topology.domain import Component

DEFAULT_START = "2026-01-01T00:00:00Z"
ACTOR = "preview"


def _as_run(plan: RunPlan) -> ScenarioRun:
    return ScenarioRun.from_plan(plan, uuid.uuid4(), 0)


def _fault_plan(arguments: argparse.Namespace, start: datetime) -> RunPlan:
    definition = SCENARIOS[arguments.scenario]
    key = arguments.target or definition.default_target
    simulated = None if key is None else SIMULATED_PLATFORM.component(key)
    if simulated is None:
        raise SystemExit(f"unknown component {key!r}")
    spec = simulated.spec
    target = Component(uuid.uuid4(), spec.key, spec.name, spec.type, spec.criticality)
    parameters: dict[str, float] = {}
    for item in arguments.param:
        name, _, raw = item.partition("=")
        try:
            parameters[name] = float(raw)
        except ValueError:
            raise SystemExit(f"--param {item!r}: value is not a number") from None
    request = StartRequest(definition, target, parameters, None)
    try:
        return plan_run(request, start, arguments.seed, ACTOR)
    except IphiError as exc:
        raise SystemExit(exc.detail) from exc


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview simulated observations offline.")
    parser.add_argument("scenario", type=ScenarioKey, choices=list(ScenarioKey))
    parser.add_argument("--target", help="Component key; defaults to the scenario's target.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ticks", type=int, default=120, help=f"1 to {MAX_TICKS} samples.")
    parser.add_argument("--start", default=DEFAULT_START, help="Scenario start, ISO 8601 UTC.")
    parser.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--format", choices=["summary", "jsonl"], default="summary")
    arguments = parser.parse_args(argv)
    if not 1 <= arguments.ticks <= MAX_TICKS or not 0 <= arguments.seed <= MAX_SEED:
        parser.error(f"--ticks must be 1..{MAX_TICKS} and --seed 0..{MAX_SEED}")
    return arguments


def _print_jsonl(ticks: list[TickObservations]) -> None:
    for observations in ticks:
        for s in observations.samples:
            record = {
                "kind": "sample",
                "observed_at": s.observed_at.isoformat(),
                "component": s.component_key,
                "metric": s.metric,
                "value": s.value,
                "unit": s.unit,
                "scenario": s.scenario_key,
                "source": s.source,
            }
            print(json.dumps(record))
        for log in observations.logs:
            record = {
                "kind": "log",
                "observed_at": log.observed_at.isoformat(),
                "component": log.component_key,
                "severity": log.severity,
                "message": log.message,
                "scenario": log.scenario_key,
                "source": log.source,
            }
            print(json.dumps(record))


def main(argv: list[str]) -> int:
    arguments = _arguments(argv)
    start = datetime.fromisoformat(arguments.start)
    if start.tzinfo is None:
        raise SystemExit("--start must carry a UTC offset, e.g. 2026-01-01T00:00:00Z")
    runs = [_as_run(baseline_plan(start, arguments.seed, ACTOR))]
    if arguments.scenario is not ScenarioKey.BASELINE:
        runs.append(_as_run(_fault_plan(arguments, start)))
    first = first_tick_at_or_after(start)
    ticks = generate_range(SIMULATED_PLATFORM, runs, first, first + arguments.ticks - 1)
    if arguments.format == "jsonl":
        _print_jsonl(ticks)
    else:
        samples = Counter(s.component_key for t in ticks for s in t.samples)
        logs = sum(len(t.logs) for t in ticks)
        print(f"scenario {arguments.scenario}, seed {arguments.seed}, {arguments.ticks} ticks")
        for component in SIMULATED_PLATFORM.components:
            print(f"  {component.key:<18} {samples[component.key]:>5} samples")
        print(f"  logs {logs}")
    print(f"fingerprint {fingerprint(ticks)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
