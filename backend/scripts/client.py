"""HTTP client of the API for the command-line tools; standard library only (runs in the image)."""

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"
REQUEST_TIMEOUT_S = 30.0
# A reset purges the history under the clock lock.
RESET_TIMEOUT_S = 300.0
POLL_INTERVAL_S = 1.0

Json = dict[str, Any]


class ToolError(Exception):
    """Unmet expectation: the tool exits non-zero with this message."""


@dataclass(frozen=True, slots=True)
class Reply:
    status: int
    body: Json
    elapsed_ms: float


class Api:
    def __init__(self, base_url: str) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ToolError(f"--base-url must be an http(s) URL, got {base_url!r}")
        self._base = base_url.rstrip("/")

    def send(
        self,
        method: str,
        path: str,
        body: Json | None = None,
        query: Mapping[str, str | int | list[str]] | None = None,
        timeout_s: float = REQUEST_TIMEOUT_S,
    ) -> Reply:
        url = self._base + path
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        # Mutations require a JSON content type (ADR 0007).
        data = None if method == "GET" else json.dumps(body or {}).encode()
        request = urllib.request.Request(  # noqa: S310 - scheme validated in __init__
            url, data=data, method=method, headers={"content-type": "application/json"}
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        # A connection dropped while reading the response is not wrapped in URLError.
        except (OSError, http.client.HTTPException) as error:
            raise ToolError(f"{method} {path}: {error}") from error
        elapsed_ms = (time.perf_counter() - started) * 1000
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:200].decode(errors="replace")}
        return Reply(status, parsed if isinstance(parsed, dict) else {"items": parsed}, elapsed_ms)

    def get(self, path: str, **query: str | int | list[str]) -> Json:
        return self.timed_get(path, **query).body

    def timed_get(self, path: str, **query: str | int | list[str]) -> Reply:
        reply = self.send("GET", API_PREFIX + path, query=query)
        self._expect(reply, "GET", path, 200)
        return reply

    def post(
        self,
        path: str,
        body: Json | None = None,
        expect: tuple[int, ...] = (200, 201),
        timeout_s: float = REQUEST_TIMEOUT_S,
        **query: str,
    ) -> Json:
        reply = self.send("POST", API_PREFIX + path, body, query, timeout_s)
        return self._expect(reply, "POST", path, *expect)

    @staticmethod
    def _expect(reply: Reply, method: str, path: str, *statuses: int) -> Json:
        if reply.status not in statuses:
            problem = reply.body.get("detail") or reply.body.get("title") or reply.body
            raise ToolError(f"{method} {path} answered {reply.status}: {problem}")
        return reply.body

    def readiness(self) -> Json | None:
        try:
            reply = self.send("GET", "/ready")
        except ToolError:
            return None
        return reply.body if reply.status == 200 else None

    def components(self) -> dict[str, Json]:
        return {item["key"]: item for item in self.get("/components")["items"]}

    def component(self, component_id: str) -> Json:
        return self.get(f"/components/{component_id}")

    def platform(self) -> Json:
        platform: Json = self.get("/platforms")["items"][0]
        return platform

    def active_incidents(self, **filters: str) -> list[Json]:
        page = self.get("/incidents", status=["open", "acknowledged"], limit=100, **filters)
        incidents: list[Json] = page["items"]
        return incidents

    def reset(self, seed: int | None = None) -> Json:
        body: Json = {} if seed is None else {"seed": seed}
        return self.post("/simulations/reset", body, timeout_s=RESET_TIMEOUT_S)

    def set_clock(self, mode: str, speed: float | None = None) -> Json:
        body: Json = {"action": "set_mode", "mode": mode}
        if speed is not None:
            body["speed"] = speed
        return self.post("/simulations/clock", body)

    def start_scenario(self, scenario_key: str, **parameters: float) -> Json:
        return self.post(
            "/simulations/scenarios", {"scenario_key": scenario_key, "parameters": parameters}
        )

    def stop_run(self, run_id: str) -> Json:
        return self.post(f"/simulations/runs/{run_id}/stop")


def wait_until[T](
    what: str,
    probe: Callable[[], T | None],
    timeout_s: float,
    interval_s: float = POLL_INTERVAL_S,
) -> T:
    deadline = time.monotonic() + timeout_s
    while True:
        value = probe()
        if value is not None:
            return value
        if time.monotonic() >= deadline:
            raise ToolError(f"not observed within {timeout_s:.0f} s: {what}")
        time.sleep(interval_s)
