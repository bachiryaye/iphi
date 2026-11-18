# Demonstration guide

How to reproduce the IPHI demonstration on your own machine, and what you should observe at each step. Everything runs against a **simulated** platform: no plant, PLC, historian or network other than your loopback interface is contacted.

## Prerequisites

- Docker Engine with the Compose plugin (v2 or later), GNU Make, `curl`
- Ports `8081`, `8001` and `5434` free on `127.0.0.1` (override with `IPHI_DEMO_FRONTEND_PORT`, `IPHI_DEMO_API_PORT`, `IPHI_DEMO_DB_PORT`)
- Nothing else: no account, no API key, no AI provider

## One command

```sh
make demo
```

This builds the images, starts a dedicated Compose project (`iphi-demo`) on a **fresh database volume**, waits for `/ready`, then runs the scripted walkthrough ([`backend/scripts/demo.py`](../backend/scripts/demo.py)) from inside the API container. The walkthrough takes about two minutes after the build. It uses the public API only, so every step goes through the same validation, mutation guard and audit log as the interface.

The script resets the simulation with seed 42, accelerates the platform clock 30 times, injects five faults in turn and **checks each expected outcome**: it exits with a non-zero status and the unmet expectation if IPHI concludes anything else. Health rules are evaluated per 5 s of platform time, so an accelerated run reaches the same conclusions as a realtime one, sooner.

A development stack started with `make up` (ports 8080, 8000, 5433) is left untouched.

## Expected output

Identifiers, evaluation values and durations vary slightly from one run to the next; states, rules, incident titles and their number do not.

```text
IPHI demo: simulated industrial data platform, no real system involved.

== 0. Clean start ==
  ok  stack ready; AI provider disabled (LLM provider 'none'; deterministic diagnosis only.)
  ok  reset with seed 42: 7 components of sim-plant-01, baseline run #2
  ..  platform unknown before the first evaluations: Not evaluated yet.
  ok  platform healthy: Priority 4: all 7 components are Healthy.
  ok  platform clock accelerated x30

== 1. Collector down -> Critical, one incident with evidence, diagnosis ==
  ..  collector_down on collector-01 (run #3)
  ok  collector-01 Critical 7 s of platform time after the fault: R-AVAIL-001 v1, last of up over 10 s = 0 from 2 samples: critical threshold breached (< 1).
  ok  INC-0001 "collector-01 unreachable" is the only active incident; downstream attached as impact: analytics-01, historian-01
  ok  platform Critical: Priority 1: a high- or medium-criticality component is Critical (collector-01).
  ok  deterministic diagnosis (iphi/deterministic-v1): 6 facts, 2 checks, 9 evidence items cited
  ..  hypothesis (low): collector-01 is the most upstream component in fault in this incident; the degradation of analytics-01, historian-01 downstream is correlated with it. Correlation along the dependency graph; causation is not proven.
  ok  INC-0001 acknowledged by dev-local
  ..  run #3 stopped; waiting for the rules to clear
  ok  INC-0001 resolved by auto_recovered (13 occurrences), platform Healthy

== 2. Latency rise -> Warning, then Critical, then stable recovery ==
  ok  edge-gateway-01 Warning: p95 of probe_latency_ms over 60 s = 297.7 ms from 12 samples: warning threshold breached (> 250 ms).
  ok  edge-gateway-01 Critical: p95 of probe_latency_ms over 60 s = 1106.8 ms from 12 samples: critical threshold breached (> 1000 ms).
  ok  INC-0002 "edge-gateway-01 probe latency high", severity critical
  ok  INC-0002 resolved by auto_recovered (6 occurrences), platform Healthy
  ok  edge-gateway-01 stayed Healthy for 3 more minutes of platform time

== 3. Stale data while the service answers -> freshness, not availability ==
  ok  INC-0003 "historian-01 process data stale" (freshness); R-AVAIL-001 stays Healthy: the service answers, its data is old
  ...
== 4. No observation at all -> Unknown, never Healthy ==
  ok  historian-01 Unknown: 0 usable up samples in the last 10 s, 1 required.
  ok  INC-0004 "historian-01 telemetry lost"; platform unknown: Priority 2: a high-criticality component is Unknown (historian-01).
  ...
== 5. Repeated errors -> one incident, growing occurrences, no storm ==
  ok  INC-0005 "data-api-01 errors elevated": 11 occurrences on one incident, severity critical
  ...
== 6. Live incident left for the interface ==
  ok  clock back to realtime; collector_down running (run #8), INC-0006 open; 6 incidents in the history

Demo passed in 113 s.
```

| Act | Scenario | What it demonstrates |
|---|---|---|
| 0 | reset, seed 42 | A seeded clean environment; `Unknown` until evidence exists, then `Healthy`; no AI provider configured |
| 1 | `collector_down` | `Critical` from a named rule version and its samples; **one** incident, downstream components attached as impact instead of opening their own; deterministic diagnosis citing stored evidence; acknowledgement; automatic resolution |
| 2 | `latency_rise` | `Warning` then `Critical` on a p95 over a window; recovery that does not flap (hysteresis) |
| 3 | `stale_data` | A freshness incident while the availability rule stays `Healthy` |
| 4 | `telemetry_blackout` | No observation gives `Unknown`, never `Healthy` |
| 5 | `error_burst` | Repeated errors update one incident (occurrence count) instead of opening a storm |
| 6 | `collector_down`, realtime | A live incident for the interface |

## Explore the interface

Open <http://127.0.0.1:8081>. The banner states that the data is simulated; the top bar carries the platform state and the monitor's own state.

1. **Overview**: the platform is `Critical` with the aggregation rule that decided it; `collector-01` shows *DOWN since*, the components downstream are marked as impacted; one active incident.
2. Open the incident: the triggering signal with its evidence points, the **evidence chain** (rule evaluations, samples and logs, each with an ID), the timeline. Press **Diagnose**: facts, a hypothesis worded as a correlation, recommended checks, each with clickable evidence chips. No AI provider is involved.
3. **Topology**: the dependency chain in the direction of the data, with the impact path.
4. **Components → collector-01**: metric history with thresholds and visible gaps, every rule with its condition, observed value and debounce.
5. **Incidents**: the five incidents resolved by the scripted acts, with their occurrence counts and resolutions.
6. **Scenarios**: stop `collector_down` and watch the incident resolve itself about five minutes later (the connectivity rule looks at a 300 s window), or set the clock to *accelerated* to shorten the wait. Start any other scenario; each card states the outcome to expect.
7. Stop the worker (`docker compose -p iphi-demo stop worker`): within about 20 s the top bar shows *Monitor stalled*, `/ready` answers 503 and states become `Unknown`: the monitor never looks healthy while blind. Start it again with `docker compose -p iphi-demo start worker`.

## Automated end-to-end tests

```sh
make install     # once: backend and frontend dependencies
cd frontend && pnpm exec playwright install chromium && cd ..   # once
make test-e2e
```

`make test-e2e` runs Playwright (Chromium) against the demo stack, started clean when it is not running; every test resets the simulation. The suite covers the mandatory scenarios 1 to 6 and 8 of the backlog (§01.1) through the interface, and measures the first display of the Overview. Scenario 7 (a viewer is refused a mutation) needs the roles of US-11.

| Test | Checks |
|---|---|
| 1 | Start `collector_down` from the Scenarios page; Overview row `Critical`; exactly one incident; evidence chain cites `R-AVAIL-001`; Diagnose renders the deterministic diagnosis |
| 2 | `latency_rise`: `Critical`, severity raised in the timeline, `Healthy` after stop, no reopening fifteen platform minutes later |
| 3 | `stale_data`: one freshness incident, no availability incident, `R-AVAIL-001` `Healthy` and `R-FRESH-001` `Critical` on the component page |
| 4 | `telemetry_blackout`: `Unknown` on the row and on the platform, never `Healthy`; one telemetry-loss incident |
| 5 | `error_burst`: at least 20 occurrences on a single active incident, grouped in the timeline |
| 6 | `/ready` reports the AI provider `disabled`; detection, incident and dashboard work |
| 8 | After `reset` with seed 42, the same fault replayed twice on a manual clock gives identical component states, deciding rules, impact and incident |
| first display | Five cold loads of the Overview, each under 2 s |

## Performance check

```sh
make perf                                  # API latency, worker cycle, detection delay
make perf PERF_ARGS="--history-days 7"     # same, with a week of stored history
```

Results measured on the development machine are in [performance.md](performance.md).

## Clean up

```sh
make demo-down    # stops the demo stack and deletes its volume
```

## Troubleshooting

- **A port is already in use**: `IPHI_DEMO_FRONTEND_PORT=9081 IPHI_DEMO_API_PORT=9001 IPHI_DEMO_DB_PORT=6434 make demo`.
- **`DEMO FAILED: not observed within N s`**: the line names the expectation that was not met. `docker compose -p iphi-demo logs worker` shows the rule and incident transitions; `curl -s http://127.0.0.1:8081/api/v1/system/status` shows the collection state. On a heavily loaded machine, lower the clock factor: `docker compose -p iphi-demo exec api python -m scripts.demo --speed 10`.
- **An e2e test times out in `reset` or before the first row appears**: PostgreSQL commits wait on `fsync`. On a spinning disk shared with other databases, a single commit was measured at 126 s, which stalls the worker and every request behind the clock lock. Stop other database containers while the suite runs (`docker compose -p iphi stop` for the development stack); `cat /proc/pressure/io` shows the I/O pressure.
- **Mutations answer `403 MUTATIONS_DISABLED`**: the stack was published on a non-loopback address (`IPHI_BIND_HOST`); unauthenticated mutations are refused there by design (ADR 0007).


## Optional diagnosis with the local fake provider (US-08)

After the standard demo/e2e run, recreate only the demo API with its fake provider:

```sh
IPHI_LLM_PROVIDER=fake IPHI_FRONTEND_PORT=8081 IPHI_API_PORT=8001 IPHI_DB_PORT=5434 \
  docker compose -p iphi-demo up -d --no-deps --force-recreate api
make wait-ready
cd frontend
IPHI_E2E_URL=http://127.0.0.1:8081 IPHI_E2E_LLM=fake \
  pnpm exec playwright test --project chromium --grep 'US-08'
```

The opt-in test confirms that the stack reports the fake provider before any diagnosis,
then resets/warms the simulation, starts `collector_down`, opens its incident, requests an
AI diagnosis, follows an evidence chip and opens the deterministic comparison. Both readings
come from the stored evidence; the fake result explicitly identifies itself as test output.
This test is skipped in the standard P0 suite unless `IPHI_E2E_LLM=fake` is set. Never run it
against a paid-provider configuration. CI uses the same two-stage none/fake procedure.

To restore the ordinary demo configuration, run the same API recreation command with
`IPHI_LLM_PROVIDER=none`. No model key is needed for either stage. Invalid output, invented
citations, provider failure/timeout, quota and concurrent requests are exercised by the
backend tests, using local fakes and an HTTP test transport.

## Incident reports (US-09)

After `make demo`, open the live incident at http://127.0.0.1:8081/incidents. Select **Export
PDF**, then **Export CSV**. Both download `IPHI-INC-…-simulated` files. The PDF contains the
incident snapshot, complete timeline, cited rule versions, stored diagnoses and evidence
register. Every page identifies the simulated environment and UTC. The CSV has one record
per proof/event, plus summary/rule/diagnosis records identified by `record_type`.

Run `cd frontend && IPHI_E2E_URL=http://127.0.0.1:8081 pnpm exec playwright test
--project chromium --grep US-09` as one command to automate both downloads. It resets the
demo simulation, injects `collector_down`, generates a deterministic diagnosis and checks
the downloaded files. Use `IPHI_LLM_PROVIDER=fake make demo` to demonstrate an explicitly
labelled local AI test result without external calls; an AI diagnosis generated before
export appears separately from its deterministic comparison.

For direct API downloads, use `GET /api/v1/reports/incidents/{incident UUID}?format=pdf|csv`.
Reports are read-only and work when mutations are disabled. Exports over 1,000 proofs or
events return `REPORT_TOO_LARGE`; use the paginated evidence/events APIs. A PDF over 100
pages can be exported as CSV if the other bounds permit. `REPORT_BUSY` means another PDF
is rendering; retry shortly. The incident and monitoring continue to work.

## Live investigation (US-07)

Use the same local demo stack. Updates arrive through SSE from committed PostgreSQL
notices; the UI refetches stored facts rather than computing health in the browser.
The two-second display target starts at a committed health transition, after the
worker's collection and hysteresis. Fault detection retains its separate latency budget.

1. Open **Topology**. Select a node with the pointer or focus it and press Enter/Space.
   Its details appear beside the graph; the URL preserves the component selection.
   Zoom/fit controls and the dependency table provide alternatives to panning.
2. Follow **Investigate**. The recorded state lanes and metric share one time window.
   Unknown is hatched; Healthy is neutral. Use the time inspector's arrows (15 s),
   Shift+arrows (60 s), Home/End and Escape. Inspect the text at the cursor, or choose
   **View states as table** and an evaluation interval. The evaluation filter is also
   stored in the URL and restored after reloading or sharing that link. Peak bins retain short Critical
   states and identify included Unknown coverage; they do not redefine current health.
3. Incident opening/resolution markers appear on the metric and below the state lanes.
   Scenario brackets use persisted run times; expand their list to read short labels.
   Annotation queries expose their latest-100 limit. The header clock is explicitly
   platform time; the monitor's cycle timestamps use wall-clock UTC.
4. Open an incident, add an **Investigation comment**, then reload to verify persistence.
   Comments also work after resolution and preserve status. More than 200 events can be
   loaded incrementally. Mutations still follow ADR 0007 before US-11.
5. Temporarily interrupt the browser connection. **Live updates paused** announces the
   30-second polling fallback. Restore connectivity, or choose **Retry live updates**:
   the initial `sync` revalidates active views, including changes missed offline.

Automated browser coverage (against the running Compose stack):

```sh
pnpm --dir frontend exec playwright test --project=chromium e2e/investigation.e2e.ts
```

`GET /api/v1/events/stream` sends bounded notices, not a replayable event archive.
There are at most 32 streams per API process; overload returns 503 and the interface
keeps polling. `GET /api/v1/components/{id}/state-history?from&to&max_segments` supports
up to seven days and 2,000 display segments per lane. More than 100,000 source evaluations
returns `413 HISTORY_TOO_DENSE`: narrow the window. A reset or missing recorded coverage
remains Unknown. See [ADR 0023](adr/0023-investigation-stream-history.md).
