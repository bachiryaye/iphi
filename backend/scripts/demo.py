"""Scripted demonstration: injects faults through the API and checks each expected outcome.

docker compose exec api python -m scripts.demo [--speed 30] [--no-live-incident]
"""

import argparse
import sys
import time
from collections.abc import Callable
from datetime import datetime

from app.core.settings import MAX_SEED
from app.simulation.domain.clock import MAX_ACCELERATION
from app.simulation.domain.platform import SIMULATED_PLATFORM
from scripts.client import DEFAULT_BASE_URL, POLL_INTERVAL_S, Api, Json, ToolError, wait_until

DEFAULT_SPEED = 30.0
DEFAULT_SEED = 42
READY_TIMEOUT_S = 180.0
# Real seconds added to each platform-time budget.
REAL_MARGIN_S = 60.0
COMPONENT_COUNT = len(SIMULATED_PLATFORM.components)
# Platform seconds, from the default rule windows and debounce.
DETECT_FAST_S = 120
RAMP_TO_CRITICAL_S = 900
RECOVERY_S = 900
STABLE_S = 180


def title(text: str) -> None:
    print(f"\n== {text} ==")


def step(text: str) -> None:
    print(f"  ..  {text}")


def ok(text: str) -> None:
    print(f"  ok  {text}")


def since_start(run: Json, at: str) -> str:
    elapsed = datetime.fromisoformat(at) - datetime.fromisoformat(run["started_at"])
    return f"{elapsed.total_seconds():.0f} s of platform time after the fault"


class Demo:
    def __init__(self, api: Api) -> None:
        self._api = api
        self._speed = 1.0
        self._ids: dict[str, str] = {}

    def set_clock(self, mode: str, speed: float | None = None) -> Json:
        clock = self._api.set_clock(mode, speed)
        self._speed = float(clock["speed"])
        return clock

    def _wait[T](self, what: str, probe: Callable[[], T | None], platform_s: float) -> T:
        return wait_until(what, probe, platform_s / self._speed + REAL_MARGIN_S)

    def component(self, key: str) -> Json:
        return self._api.component(self._ids[key])

    def wait_state(self, key: str, states: set[str], platform_s: float) -> Json:
        def probe() -> Json | None:
            component = self.component(key)
            return component if component["health"]["state"] in states else None

        return self._wait(f"{key} {' or '.join(sorted(states))}", probe, platform_s)

    def wait_incident(self, key: str, failure_class: str, platform_s: float) -> Json:
        def probe() -> Json | None:
            found = self._api.active_incidents(
                component_id=self._ids[key], failure_class=failure_class
            )
            return found[0] if found else None

        return self._wait(f"active {failure_class} incident on {key}", probe, platform_s)

    def wait_recovered(self, incident_id: str) -> Json:
        def probe() -> Json | None:
            incident = self._api.get(f"/incidents/{incident_id}")
            if incident["status"] != "resolved":
                return None
            return incident if self._api.platform()["health"]["state"] == "healthy" else None

        return self._wait("incident auto-resolved and platform Healthy", probe, RECOVERY_S)

    def expect_single_incident(self, incident: Json) -> None:
        active = self._api.active_incidents()
        if [item["id"] for item in active] != [incident["id"]]:
            listed = ", ".join(f"{i['reference']} {i['title']}" for i in active)
            raise ToolError(f"expected {incident['reference']} alone, active: {listed}")

    def expect_stable(self, key: str) -> None:
        deadline = time.monotonic() + STABLE_S / self._speed
        while time.monotonic() < deadline:
            state = self.component(key)["health"]["state"]
            if state != "healthy":
                raise ToolError(f"{key} went back to {state} after recovering")
            time.sleep(POLL_INTERVAL_S)
        ok(f"{key} stayed Healthy for {STABLE_S // 60} more minutes of platform time")

    def start(self, scenario_key: str, target: str, detail: str = "") -> Json:
        run = self._api.start_scenario(scenario_key)
        step(f"{scenario_key} on {target} (run #{run['number']}){detail}")
        return run

    def stop_and_recover(self, run: Json, incident: Json) -> None:
        self._api.stop_run(run["id"])
        step(f"run #{run['number']} stopped; waiting for the rules to clear")
        resolved = self.wait_recovered(incident["id"])
        ok(
            f"{resolved['reference']} resolved by {resolved['resolution']} "
            f"({resolved['occurrence_count']} occurrences), platform Healthy"
        )

    def clean_start(self, seed: int, speed: float) -> None:
        title("0. Clean start")
        readiness = wait_until("stack ready (GET /ready 200)", self._api.readiness, READY_TIMEOUT_S)
        ai = next(check for check in readiness["checks"] if check["name"] == "ai_provider")
        ok(f"stack ready; AI provider {ai['status']} ({ai['detail']})")
        reset = self._api.reset(seed)
        self._speed = float(reset["clock"]["speed"])
        components = self._api.components()
        if len(components) != COMPONENT_COUNT:
            raise ToolError(f"expected {COMPONENT_COUNT} components, found {len(components)}")
        self._ids = {key: item["id"] for key, item in components.items()}
        ok(
            f"reset with seed {reset['clock']['seed']}: {len(components)} components of "
            f"{SIMULATED_PLATFORM.key}, baseline run #{reset['baseline_run']['number']}"
        )
        first = self._api.platform()["health"]
        step(f"platform {first['state']} before the first evaluations: {first['rationale']}")

        def healthy() -> Json | None:
            health: Json = self._api.platform()["health"]
            return health if health["counts"]["healthy"] == COMPONENT_COUNT else None

        health = self._wait("all components Healthy", healthy, DETECT_FAST_S)
        ok(f"platform {health['state']}: {health['rationale']}")
        clock = self.set_clock("accelerated", speed)
        ok(f"platform clock {clock['mode']} x{clock['speed']:g}")

    def collector_down(self) -> None:
        title("1. Collector down -> Critical, one incident with evidence, diagnosis")
        run = self.start("collector_down", "collector-01")
        component = self.wait_state("collector-01", {"critical"}, DETECT_FAST_S)
        reason = component["reason"]
        ok(
            f"collector-01 Critical {since_start(run, reason['evaluated_at'])}: "
            f"{reason['rule']['key']} v{reason['rule']['version']}, {reason['explanation']}"
        )
        incident = self.wait_incident("collector-01", "availability", DETECT_FAST_S)
        impacted = self.wait_impact(incident["id"])
        self.expect_single_incident(incident)
        ok(
            f'{incident["reference"]} "{incident["title"]}" is the only active incident; '
            f"downstream attached as impact: {', '.join(impacted)}"
        )
        platform = self._api.platform()["health"]
        if platform["state"] != "critical":
            raise ToolError(f"platform is {platform['state']}, expected critical")
        ok(f"platform Critical: {platform['rationale']}")

        diagnosis = self._api.post(f"/incidents/{incident['id']}/diagnose", mode="deterministic")
        cited = {
            citation["label"]
            for section in ("observed_facts", "hypotheses", "recommended_checks")
            for claim in diagnosis[section]
            for citation in claim["evidence"]
        }
        hypothesis = diagnosis["hypotheses"][0]
        ok(
            f"deterministic diagnosis ({diagnosis['model']}): "
            f"{len(diagnosis['observed_facts'])} facts, {len(diagnosis['recommended_checks'])} "
            f"checks, {len(cited)} evidence items cited"
        )
        step(f"hypothesis ({hypothesis['uncertainty']}): {hypothesis['text']}")
        acknowledged = self._api.post(f"/incidents/{incident['id']}/ack")
        ok(f"{acknowledged['reference']} acknowledged by {acknowledged['acknowledged_by']}")
        self.stop_and_recover(run, incident)

    def wait_impact(self, incident_id: str) -> list[str]:
        def probe() -> list[str] | None:
            impacted = self._api.get(f"/incidents/{incident_id}")["impacted"]
            return [item["component"]["key"] for item in impacted] or None

        return self._wait("downstream impact on the incident", probe, DETECT_FAST_S)

    def latency_rise(self) -> None:
        title("2. Latency rise -> Warning, then Critical, then stable recovery")
        run = self.start("latency_rise", "edge-gateway-01", ", 5 min ramp to 1 500 ms")
        warning = self.wait_state("edge-gateway-01", {"warning", "critical"}, RAMP_TO_CRITICAL_S)
        ok(
            f"edge-gateway-01 {warning['health']['state'].capitalize()}: "
            f"{warning['reason']['explanation']}"
        )
        critical = self.wait_state("edge-gateway-01", {"critical"}, RAMP_TO_CRITICAL_S)
        ok(f"edge-gateway-01 Critical: {critical['reason']['explanation']}")
        incident = self.wait_incident("edge-gateway-01", "latency", DETECT_FAST_S)
        self.expect_single_incident(incident)
        ok(f'{incident["reference"]} "{incident["title"]}", severity {incident["severity"]}')
        self.stop_and_recover(run, incident)
        self.expect_stable("edge-gateway-01")

    def stale_data(self) -> None:
        title("3. Stale data while the service answers -> freshness, not availability")
        run = self.start("stale_data", "historian-01")
        incident = self.wait_incident("historian-01", "freshness", RAMP_TO_CRITICAL_S)
        component = self.wait_state("historian-01", {"critical"}, RAMP_TO_CRITICAL_S)
        self.expect_single_incident(incident)
        rules = self._api.get(f"/components/{component['id']}/health")["rules"]
        availability = next(rule for rule in rules if rule["rule"]["key"] == "R-AVAIL-001")
        if availability["health"]["state"] != "healthy":
            raise ToolError(
                f"R-AVAIL-001 is {availability['health']['state']}: the probe should answer"
            )
        ok(
            f'{incident["reference"]} "{incident["title"]}" ({incident["failure_class"]}); '
            f"R-AVAIL-001 stays Healthy: the service answers, its data is old"
        )
        ok(
            f"historian-01 {component['health']['state'].capitalize()}: "
            f"{component['reason']['explanation']}"
        )
        self.stop_and_recover(run, incident)

    def telemetry_blackout(self) -> None:
        title("4. No observation at all -> Unknown, never Healthy")
        run = self.start("telemetry_blackout", "historian-01")
        component = self.wait_state("historian-01", {"unknown"}, DETECT_FAST_S)
        ok(f"historian-01 Unknown: {component['reason']['explanation']}")
        incident = self.wait_incident("historian-01", "telemetry_loss", DETECT_FAST_S)
        platform = self._api.platform()["health"]
        ok(
            f'{incident["reference"]} "{incident["title"]}"; platform {platform["state"]}: '
            f"{platform['rationale']}"
        )
        self.stop_and_recover(run, incident)

    def error_burst(self) -> None:
        title("5. Repeated errors -> one incident, growing occurrences, no storm")
        run = self.start("error_burst", "data-api-01")
        incident = self.wait_incident("data-api-01", "errors", DETECT_FAST_S)

        def grown() -> Json | None:
            current = self._api.get(f"/incidents/{incident['id']}")
            return current if current["occurrence_count"] >= 10 else None

        current = self._wait("occurrence count >= 10", grown, RAMP_TO_CRITICAL_S)
        self.expect_single_incident(incident)
        ok(
            f'{current["reference"]} "{current["title"]}": {current["occurrence_count"]} '
            f"occurrences on one incident, severity {current['severity']}"
        )
        self.stop_and_recover(run, incident)

    def leave_live_incident(self) -> None:
        title("6. Live incident left for the interface")
        clock = self.set_clock("realtime")
        run = self._api.start_scenario("collector_down")
        incident = self.wait_incident("collector-01", "availability", DETECT_FAST_S)
        total = len(self._api.get("/incidents", limit=100)["items"])
        ok(
            f"clock back to {clock['mode']}; collector_down running (run #{run['number']}), "
            f"{incident['reference']} {incident['status']}; {total} incidents in the history"
        )


def _stop_faults(api: Api) -> None:
    try:
        for active in api.get("/simulations/runs", status="active")["items"]:
            if active["scenario_key"] != "baseline":
                api.stop_run(active["id"])
        api.set_clock("realtime")
    except ToolError as failure:
        print(f"  !!  could not restore the stack after the failure: {failure}", file=sys.stderr)


def run(api: Api, speed: float, seed: int, leave_live: bool) -> None:
    print("IPHI demo: simulated industrial data platform, no real system involved.")
    demo = Demo(api)
    started = time.monotonic()
    try:
        demo.clean_start(seed, speed)
        demo.collector_down()
        demo.latency_rise()
        demo.stale_data()
        demo.telemetry_blackout()
        demo.error_burst()
    except ToolError:
        # The stack stays up for investigation: realtime, no fault running.
        _stop_faults(api)
        raise
    if leave_live:
        demo.leave_live_incident()
    else:
        demo.set_clock("realtime")
    print(f"\nDemo passed in {time.monotonic() - started:.0f} s.")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run the scripted IPHI demonstration.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API root, without /api/v1.")
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_SPEED,
        help=f"Clock factor, 2 to {MAX_ACCELERATION:g}.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--no-live-incident",
        action="store_true",
        help="End with a healthy platform instead of leaving collector_down running.",
    )
    arguments = parser.parse_args(argv)
    if not 2 <= arguments.speed <= MAX_ACCELERATION or not 0 <= arguments.seed <= MAX_SEED:
        parser.error(f"--speed must be 2..{MAX_ACCELERATION:g} and --seed 0..{MAX_SEED}")
    try:
        run(
            Api(arguments.base_url), arguments.speed, arguments.seed, not arguments.no_live_incident
        )
    except ToolError as failure:
        print(f"\nDEMO FAILED: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
