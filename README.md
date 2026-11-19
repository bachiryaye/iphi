# IPHI — Industrial Platform Health Intelligence

IPHI monitors the health of an **industrial data platform** — sources, gateway, collector, historian, database, API — rather than the machines it measures. It ingests metrics and logs, computes explainable health states (`Healthy`, `Warning`, `Critical`, `Unknown`), opens deduplicated incidents backed by stored evidence, and can add an evidence-grounded diagnosis.

> **Simulated data.** IPHI runs against a simulated infrastructure. It is not connected to any real plant, PLC or historian, claims no compatibility with any commercial product (AVEVA PI included), and is not production software. Every simulated observation is labelled as such in the UI, the API and exports.

## Status

| Story | Scope | State |
|---|---|---|
| US-01 | One-command stack, migrations, readiness, CI, app shell | Delivered |
| US-02 | Seven-component simulated platform, deterministic generator, nine scenarios, platform clock | Delivered |
| US-03 | Validated ingestion, PostgreSQL history, metric and log APIs, collection monitoring | Delivered |
| US-04 | Versioned health rules, hysteresis, `Unknown`, component and platform health with justification | Delivered |
| US-05 | Deduplicated incidents with evidence, lifecycle, downstream suppression, deterministic diagnosis | Delivered |
| US-06 | Operator dashboard: Overview, Topology, Components, Incidents, Scenarios, Rules | Delivered |
| US-10 | One-command reproducible demo, end-to-end tests of the mandatory scenarios, performance check, case study | Delivered |
| US-08 | Optional structured diagnosis, evidence validation, deterministic comparison and fallback | Delivered (PR #8; CI green on main) |
| US-09 | Incident PDF and CSV reports from stored evidence | Delivered (PR #9; main CI 44248348754 green) |
| US-07 | Live updates, interactive topology, recorded state history and investigation comments | Delivered (PR #10; CI green on main) |
| US-11 | Server sessions, roles, CSRF, audit and permission tests | Implemented (PR #12; CI green, [access guide](docs/access.md)) |
| US-12 | MQTT adapter with a real broker and synthetic publisher | In progress ([MQTT guide](docs/mqtt.md)) |

What runs today: PostgreSQL, a migration and seed job, the FastAPI API (`/health`, `/ready`, simulation, metrics, logs, health and system status endpoints, OpenAPI), a worker that holds the scheduler lock and, every cycle, collects the simulated observations, validates and stores them, evaluates the health rules, opens, updates and resolves incidents, purges data past retention and writes a heartbeat, and the operator dashboard described below.

![Overview during the collector_down scenario, light theme](docs/design/screenshots/overview-light-1440.png)

| Incident with its evidence chain and deterministic diagnosis | Same Overview, dark theme |
|---|---|
| ![Incident page: signal, evidence chain, diagnosis, timeline](docs/design/screenshots/incident-light-1440.png) | ![Overview, dark theme](docs/design/screenshots/overview-dark-1440.png) |

Screenshots are taken from the running application by `make screenshots`; more in [`docs/design/screenshots/`](docs/design/screenshots/).

## Demo in one command

```sh
make demo
```

Starts a clean, seeded stack in its own Compose project (fresh volume, http://127.0.0.1:8081), then injects five faults on an accelerated platform clock and **checks what IPHI concludes** for each: collector outage (one incident with evidence, downstream attached as impact, deterministic diagnosis), latency rise and stable recovery, stale data distinct from availability, telemetry blackout (`Unknown`, never `Healthy`), error burst without incident storm. It takes about two minutes after the build, needs no external account or API key; local demo accounts are initialized automatically, and leaves a live incident to explore in the interface. The step-by-step guide with the expected output is in [docs/demo.md](docs/demo.md); the reasoning behind the design is in the [case study](docs/case-study.md).

## Architecture

```mermaid
flowchart LR
  subgraph sim["Simulated platform sim-plant-01 (no real system)"]
    direction LR
    plc[plc-sim-01] --> gw[edge-gateway-01] --> col[collector-01] --> hist[historian-01] --> dapi[data-api-01] --> ana[analytics-01]
    hist -.- tsdb[(timeseries-db-01)]
  end
  subgraph worker["Worker: one cycle every 5 s, one transaction"]
    direction LR
    conn[Connectors] --> ing[Ingestion<br/>validate, deduplicate] --> health[Health rules<br/>hysteresis, Unknown] --> inc[Incidents<br/>fingerprint, evidence]
  end
  sim -- "metrics and logs<br/>source = simulation" --> conn
  ing --> pg[(PostgreSQL)]
  health --> pg
  inc --> pg
  pg --> api[FastAPI /api/v1<br/>OpenAPI, deterministic diagnosis]
  api --> ui[React dashboard<br/>behind Nginx]
  clock[Platform clock<br/>realtime, accelerated, manual] -.-> sim
  clock -.-> worker
```

One PostgreSQL, one API process, one worker holding the scheduler lock: a modular monolith whose module boundaries (simulation, connectors, ingestion, health, incidents, diagnostics) are enforced by import contracts in CI. The worker alone collects and evaluates; the API serves the results and records operator actions (acknowledge, resolve, diagnose, scenarios, clock). Details in the [architecture document](docs/02-architecture-technique.md) and the [decision records](docs/adr/README.md).

## Incident reports

On an incident page, **Export PDF** and **Export CSV** download a snapshot of its stored
facts, timeline, evidence and versioned rules. Stored deterministic and AI diagnoses are
separate; AI output carries a verification label and its comparison or fallback reference.
Export does not call a model or change the incident. No diagnosis yet is a valid report state.
Real captures: [download controls](docs/design/screenshots/us-09-exports-light-1440.png) and
[PDF first page](docs/design/screenshots/us-09-report-first-page.png).

The read-only endpoint is `GET /api/v1/reports/incidents/{id}?format=pdf|csv` (PDF by default).
All pages/rows identify the simulated environment; timestamps are UTC, with the wall-clock
export time distinguished from the simulated platform time. CSV uses UTF-8 with BOM and a
`record_type` column (`summary`, `event`, `evidence`, `rule`, `diagnostic_meta`, `diagnostic`).
Spreadsheet formula prefixes are protected by an apostrophe, preserving the database value.

Reports include every attached proof/event up to 1,000 of each; larger incidents receive
`413 REPORT_TOO_LARGE` and remain accessible through the paginated incident APIs. PDF content
is limited to 2 MB of HTML, 100 pages and one simultaneous render per API process (`503
REPORT_BUSY`); CSV remains available during rendering. Downloads are capped at 8 MB. The PDF
uses bundled IBM Plex fonts and refuses external resources. Details: [ADR 0022](docs/adr/0022-rapports-incidents-us09.md).

The Docker image includes Pango. For backend development outside containers, install
`libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0` on Debian/Ubuntu before running the PDF
tests; see the [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)
for other systems. Non-PDF endpoints do not load the native rendering library.

## Requirements

- Docker Engine with the Compose plugin (v2 or later), GNU Make and Python 3.10+
- For local development outside containers: [uv](https://docs.astral.sh/uv/) ≥ 0.13, Node.js ≥ 24, pnpm 12, GNU Make

## Run

```sh
make up                         # generates missing local credentials, builds and starts
# Direct Compose: make init-env && docker compose up --build
```

| Service | Address | Role |
|---|---|---|
| frontend | http://127.0.0.1:8080 | Static build behind Nginx; proxies `/api`, `/health`, `/ready` |
| api | http://127.0.0.1:8000/docs | FastAPI, OpenAPI at `/api/v1/openapi.json` |
| db | 127.0.0.1:5433 | PostgreSQL 16 |
| migrate | — | `alembic upgrade head`, idempotent seed (topology, clock, baseline run), then exits |
| worker | — | Single scheduler (PostgreSQL advisory lock), heartbeat every 5 s |

All ports bind to `127.0.0.1` (`IPHI_BIND_HOST` moves the API and frontend; the database stays local). `make init-env` creates missing demo passwords in an ignored mode-600 `.env`; existing configuration is preserved. Sign in with the local `viewer`, `engineer` or `admin` account. See [sessions, roles and API access](docs/access.md).

Check the stack:

```sh
curl -i http://127.0.0.1:8000/health   # 200 {"status":"ok"}
curl -i http://127.0.0.1:8000/ready    # 200 once migrated and the worker has cycled, 503 otherwise
```

`/ready` reports four checks: database reachable, schema at the code's migration head, worker heartbeat younger than three cycles, optional AI provider (off by default; last persisted attempt when configured). Only the database, schema and worker checks determine readiness. Stop the worker (`docker compose stop worker`) and the readiness turns `503`, and the top bar shows *Monitor stalled*: the monitor never looks healthy while blind.

## Run without Compose

The images start on their own entry point (ADR 0020): `iphi-backend` takes a role, `api` by default, `worker` or `migrate`; `iphi-frontend` proxies to `IPHI_API_UPSTREAM`. Both run as non-root on a read-only root filesystem with a writable `/tmp`, and carry a healthcheck (the worker's checks its last completed cycle).

```sh
docker run --rm -e IPHI_DATABASE_URL=… iphi-backend:local migrate     # once per release
docker run -d -e IPHI_DATABASE_URL=… iphi-backend:local               # api, port 8000
docker run -d -e IPHI_DATABASE_URL=… iphi-backend:local worker        # a single active worker
docker run -d -e IPHI_API_UPSTREAM=http://<api-host>:8000 -p 8080:8080 iphi-frontend:local
```

`IPHI_MIGRATE_ON_START=true` runs the migration at the start of `api` or `worker` instead; concurrent starts migrate one after the other. Supply the three `IPHI_DEMO_*_PASSWORD` values to the migration job to initialize local accounts. Operational reads require a session; mutations additionally require the appropriate role and CSRF proof. Local HTTP requires loopback binding; `IPHI_DEPLOYMENT_MODE=production` enables Secure cookies and needs an HTTPS ingress (ADR 0025).

## Simulation

The simulated platform (`sim-plant-01`) has seven components — `plc-sim-01 → edge-gateway-01 → collector-01 → historian-01 (+ timeseries-db-01) → data-api-01 → analytics-01` — each probed every 5 s of **platform time** (`up`, `probe_latency_ms`, plus load, queue, data age and error metrics depending on its type). Values are a pure function of seed, component, metric, sample slot and the scenario runs covering it: the same inputs give the same observations, in any order and after any restart.

| Scenario | Default target | Expected outcome (default rules) |
|---|---|---|
| `baseline` | all | Healthy everywhere; always running |
| `collector_down` | collector-01 | Critical, downstream impacted, one availability incident |
| `latency_rise` | edge-gateway-01 | Warning then Critical, one latency incident |
| `stale_data` | historian-01 | Service up, data ageing, one freshness incident |
| `intermittent_loss` | edge-gateway-01 | Isolated probe failures, one connectivity incident |
| `error_burst` | data-api-01 | Repeated errors, one incident with growing occurrences |
| `resource_pressure` | timeseries-db-01 | CPU and memory above 90 %, one resources incident |
| `backlog_growth` | collector-01 | Growing queue, one backlog incident |
| `telemetry_blackout` | historian-01 | No observation at all, Unknown, one telemetry-loss incident |

First initialize the authenticated `iphi_request` helper from the [API access guide](docs/access.md#authenticated-api-examples).

```sh
B=http://127.0.0.1:8080/api/v1/simulations
iphi_request $B/scenarios                                   # catalog, parameters, expected outcomes
iphi_request -X POST $B/scenarios -H 'content-type: application/json' \
     -d '{"scenario_key": "latency_rise", "parameters": {"peak_ms": 2000}, "duration_s": 600}'
iphi_request "$B/runs?status=active"                        # runs, newest first (cursor pagination)
iphi_request -X POST $B/clock -H 'content-type: application/json' \
     -d '{"action": "set_mode", "mode": "accelerated", "speed": 10}'   # realtime | accelerated | manual
iphi_request -X POST $B/reset -H 'content-type: application/json'   # stop runs, realtime clock, fresh baseline
```

Mutations require a signed-in engineer or admin; reset requires admin. Each requires a session-bound CSRF header and `Content-Type: application/json`, including bodyless requests. Cross-site browser requests are refused, Host values are restricted to `IPHI_ALLOWED_HOSTS`, and sensitive actions and permission refusals are audited.

Preview the generator without a database; the printed fingerprint is the one checked by the golden test:

```sh
cd backend && uv run python -m scripts.simulate collector_down --ticks 120
# fingerprint df67ef15df8ffe50249e2e5d18982eeefc027c3fff9ae90584c7faf134152cbc
```

## Observations

The optional [MQTT simulation](docs/mqtt.md) runs the same pipeline through a real Mosquitto
broker and separate synthetic publisher: `make mqtt-up` opens its isolated dashboard on port
8082, and `make mqtt-demo` runs the acceptance walkthrough through MQTT. Observations carry
`source=mqtt`, always in `environment=simulation`. The default stack uses direct simulation;
only one transport is selected at a time. No real industrial compatibility is claimed.

Every cycle the worker collects each elapsed 5 s sample slot once (also in accelerated time), validates it and stores it in PostgreSQL, with `observed_at` (event time) and `received_at` (ingestion time), `source=simulation` and the scenario run that shaped it. Invalid observations are rejected and counted per code (unknown component or metric, wrong unit, out of range, more than 30 s in the future, more than 10 min late, oversized log); re-delivered ones are ignored and counted. A failing connector is recorded as a failed collection run without stopping the cycle. Observations older than `IPHI_RETENTION_DAYS` (7) are purged; `reset` purges the simulated history.

```sh
A=http://127.0.0.1:8080/api/v1
iphi_request $A/system/status            # clock, worker cycle, collection state and recent runs
iphi_request $A/metrics/catalog          # metric names, units, accepted ranges
C=$(docker compose exec -T db psql -U iphi -Atc "SELECT id FROM component WHERE key='collector-01'")
iphi_request "$A/metrics?component_id=$C&metric_name=probe_latency_ms&max_points=200"
iphi_request "$A/logs?component_id=$C&min_severity=warning&limit=20"
```

`GET /metrics` returns raw samples while the window holds at most `max_points` (≤ 2000), otherwise min/avg/max buckets; windows are limited to 7 days, and stretches without data come back as explicit `gaps`, never interpolated. Component IDs are listed by `GET /components`.

## Health

Nine default rules in [`backend/config/health_rules.yaml`](backend/config/health_rules.yaml) (availability, connectivity ratio, p95 latency, process-data freshness, errors, CPU, memory, backlog, telemetry loss) are evaluated at every 5 s sample slot of platform time, so the state history is the same in realtime, accelerated or manual mode. Each rule has warning and critical thresholds with distinct clear thresholds, and needs `raise_after` consecutive evaluations to get worse and `clear_after` to recover: a value oscillating inside the band never changes the state. A rule without samples in its window is `Unknown`, never `Healthy`; a component that stops answering its probe is `Critical`, one IPHI no longer observes at all is `Unknown`.

A component takes the worst state of its rules (`Critical > Unknown > Warning > Healthy`); components downstream of a `Critical` or `Unknown` one are marked as impacted without changing their own state. The platform state follows a priority table, never an average: a high- or medium-criticality component `Critical` makes it `Critical`, a high one `Unknown` makes it `Unknown`, any other degradation `Warning`. Thresholds are demonstration values, not industrial recommendations; changing one in the file creates a new rule version at the next bootstrap.

```sh
iphi_request $A/platforms                    # aggregated state, counts, priority line applied
iphi_request "$A/components?state=critical"  # current state, deciding evaluation, impacted_by
iphi_request $A/components/$C/health         # every rule: threshold, window, value, evidence, debounce
iphi_request "$A/rule-evaluations?component_id=$C&rule_key=R-LAT-001"   # stored evaluations
iphi_request $A/health-rules                 # active rule versions (read-only)
```

Every state cites its rule version, window, threshold, observed value and the IDs of the samples behind it. If the worker stops evaluating, the API reports `unknown` with `stale: true` instead of the last computed state.

## Incidents

When a rule turns `Warning` or `Critical` (or a component that was observed goes silent), the worker opens an incident, fingerprinted by platform, component and failure class: a database index guarantees at most one active incident per fingerprint, so a persistent fault updates the same incident (occurrences, severity up or down) instead of opening new ones. An incident resolves itself once every rule it covers is back to `Healthy`; the same failure within 15 minutes of platform time reopens it. Losing connectivity on an unreachable component is part of the same incident. Alerts of components downstream of an unreachable or silent one are attached to the upstream incident as impact rather than opening their own.

Every incident links the rule evaluations behind it and the samples and logs they cite; these are kept by retention and by `reset`, which closes active incidents (`resolution: reset`). The timeline (opened, occurrences, severity changes, acknowledgement, resolution, reopening, suppressed downstream alerts, diagnoses) is append-only.

```sh
iphi_request "$A/incidents?status=open&status=acknowledged"    # newest first, cursor pagination
I=$(iphi_request "$A/incidents?status=open" | python3 -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["id"])')
iphi_request $A/incidents/$I                     # covered rules, evidence (E1…En), timeline
iphi_request -X POST $A/incidents/$I/ack -H 'content-type: application/json'
iphi_request -X POST "$A/incidents/$I/diagnose?mode=deterministic" -H 'content-type: application/json'
iphi_request -X POST $A/incidents/$I/resolve -H 'content-type: application/json' \
     -d '{"comment": "Collector restarted."}'   # 409 while the condition is still active
```

The deterministic diagnosis lists observed facts, a hypothesis (the most upstream component in fault, always worded as a correlation) and the checks recommended by the rules involved, each citing its evidence; it needs no AI provider. Acknowledgement, resolution and diagnosis follow the same mutation guard as the simulation and are audited.

### Optional AI diagnosis (US-08)

`IPHI_LLM_PROVIDER=none` remains the default. The **Diagnose** action always builds a
reading from stored evidence without a model. **AI diagnosis** adds a separately labeled
result, clickable evidence, uncertainty, removed claims and a deterministic comparison from
the same evidence snapshot. A rejected response or provider failure shows that deterministic
fallback immediately; collection, health, incidents and `/ready` keep working independently.

To try the local **fake provider**, with no account, network request or cost:

```sh
IPHI_LLM_PROVIDER=fake docker compose up --build -d
```

Open an incident and choose **AI diagnosis**. The panel explicitly says that it is local test
output and no language model was called. Use **Compare with deterministic diagnosis** to
inspect the same observations through the deterministic reading.

| Local fake diagnosis, light theme | Same panel, dark theme |
|---|---|
| ![Fake-provider diagnosis with citations and explicit simulation limitations](docs/design/screenshots/us-08-diagnosis-light-1440.png) | ![The same diagnosis in the dark theme](docs/design/screenshots/us-08-diagnosis-dark-1440.png) |

For **free OpenRouter models**, put these settings in your ignored local `.env` and
supply your own `IPHI_LLM_API_KEY` there:

```dotenv
IPHI_LLM_PROVIDER=openrouter
IPHI_LLM_MODEL=particle-ai/particle-1:free
IPHI_LLM_REASONING_EFFORT=none
```

This model accepts reasoning effort `none`. For another model, restore
`IPHI_LLM_REASONING_EFFORT=default` or choose an effort it supports; mandatory-reasoning
models can spend the whole output budget before producing an answer. `openrouter/free`
automatically selects a free model, but capacity and structured-output support vary.
The adapter accepts only that free router or explicit `:free` variants, sets a zero
price ceiling, disables plugins, and rejects missing/nonzero reported usage cost. It
never switches to a paid route. Rate limits or unavailable free capacity show the
existing deterministic fallback. See [ADR 0024](docs/adr/0024-openrouter-free-us08.md).

The separate OpenAI adapter uses `IPHI_LLM_PROVIDER=openai` and a configured model with
structured-output support; **live paid calls have not been tested**. Neither adapter
has a default paid model or bundled credential. The credential is passed only to the
API container. Free-provider data policies still apply: use simulated evidence only.

The server uses a fixed HTTPS endpoint, exposes no tools, and applies a shared deadline
(maximum 20 s, at most one retry), input/output caps and a persisted six-attempt/60 s actor
budget. Retried requests with the same `Idempotency-Key` reuse the stored result; conflicting
modes return 409, concurrent AI requests 409, and exhausted budget 429.

All provider input is bounded and redacted; rejected raw text and provider exception bodies
are not logged. The API exposes status, error code, token usage when available, latency and
`deterministic_id`, rather than the persisted prompt. Provider status describes its last
attempt, not a live availability probe. Citation validation establishes a reference, **not
factual truth or causation**. Pattern-based redaction cannot recognize every possible secret;
keep this demonstrator on simulated data. Configuration and limits:
[ADR 0021](docs/adr/0021-diagnostic-llm-us08.md),
[diagnosis threat model](docs/security/diagnostics-threat-model.md).

## Dashboard

Open http://127.0.0.1:8080. Active views refetch stored facts after committed SSE notices. If the stream is unavailable, an explicit banner announces the 30 s polling fallback; reconnection revalidates the views. Failed refreshes keep the previous data visibly stale. The top bar carries platform time, platform health and the monitor's own state.

| View | What it answers |
|---|---|
| Overview | Platform state with the aggregation rationale, components by state, active incidents, one row per component with its key metric drawn against its thresholds (chosen by the API) |
| Topology | Interactive dependency chain with zoom, keyboard selection, a component panel and a table equivalent |
| Components / Component | Header with the rule behind the state, recorded component/rule state bands aligned with metrics (shared cursor, incident/scenario markers, shareable evaluation filter), metric thresholds and visible gaps (15 min to 24 h, table view), every rule with its condition, observed value and debounce, recent logs grouped by fingerprint, dependencies, recent incidents |
| Incidents / Incident | Filterable list (filters in the URL, cursor pages); the incident page shows the triggering signal, the immutable evidence chain, the deterministic diagnosis with clickable evidence chips, the paginated timeline with grouped occurrences and investigation comments, and Acknowledge, Resolve and Diagnose |
| Scenarios | The fault catalog with each expected outcome, start and stop, the platform clock (mode, speed, advance in manual mode) and reset with an in-page confirmation |
| Rules | The active rule versions: measure, thresholds and clear levels, debounce, targets, rationale |
| Audit (admin) | Sensitive actions and denied attempts, actor, UTC time, result, correlation ID, filters and cursor pages |

Operational controls are visible but disabled with the required role explained. Audit navigation is admin-only; server permissions apply even when a caller bypasses the UI (ADR 0025).

Actual US-07 captures: [topology](docs/design/screenshots/us-07-topology-light-1440.png), [recorded states and metrics](docs/design/screenshots/us-07-component-light-1440.png), [dark theme at 768 px](docs/design/screenshots/us-07-component-dark-768.png).

## Develop and test

```sh
make install     # uv sync + pnpm install from the lockfiles
make check       # lint, type checks, tests, API client drift — what CI runs
make help        # every target
```

- Backend tests run against real PostgreSQL (`make test-backend` starts `db`; each test gets a fresh database). MQTT integration tests also create a disposable Mosquitto container; Docker is required. `make test-mqtt` runs just the MQTT contract and integration tests.
- Frontend tests use Vitest, Testing Library and axe-core (every screen is checked for serious accessibility violations).
- End-to-end: `make test-e2e` runs Playwright (Chromium) against the demo stack (started clean when it is not running): all eight mandatory scenarios of the backlog, including viewer refusal and admin audit through the interface, and the first display of the Overview (once: `cd frontend && pnpm exec playwright install chromium`).
- `make demo` is itself an executable acceptance test of the API path: it exits non-zero when an expected state, incident or diagnosis is not observed.
- Performance: `make perf` measures API latency, worker cycle duration and detection delay against the targets of the architecture; results in [docs/performance.md](docs/performance.md).
- The TypeScript API types are generated from the backend OpenAPI document (`make api-client`); CI fails if they drift.
- Frontend dev server with hot reload: `cd frontend && pnpm dev` (http://127.0.0.1:5173, proxied to the API on port 8000).

## Repository layout

```text
backend/    FastAPI app (app/), Alembic migrations, tests (unit + PostgreSQL integration)
frontend/   React + TypeScript + Vite, Tailwind tokens from the design system
docs/       Requirements, architecture, backlog, design system, ADRs (French)
```

## Documentation

For an evaluator, in English: [demonstration guide](docs/demo.md), [case study](docs/case-study.md) (problem, decisions, trade-offs, limits), [measured performance](docs/performance.md), [three-minute video script](docs/video-script.md).

The design dossier is in French: [requirements](docs/01-cahier-des-charges.md), [architecture](docs/02-architecture-technique.md), [backlog](docs/03-backlog.md), [design system](docs/04-design-system.md), [decision records](docs/adr/README.md). Engineering rules: [rules.md](rules.md).

## Limitations

- SSE notices have no durable replay: every connection resynchronizes active views, with a 30 s polling fallback. Streams and state-history reads are bounded ([ADR 0023](docs/adr/0023-investigation-stream-history.md)). Optional AI diagnosis is available through US-08.
- Downstream suppression can hide a second, independent fault downstream: its evidence stays attached to the upstream incident as impact.
- An observation arriving late, after its sample slot was evaluated, does not trigger a re-evaluation of that slot.
- After the worker has been stopped for more than 10 minutes of platform time, the missed sample slots are not backfilled: they remain a visible gap.
- Simulation simplifications: `stale_data` does not age downstream data; one fault scenario per component at a time.
- Identity supports a local demonstrator, with an eight-hour session and a conservative shared login limit; no account-management UI or public deployment is included (ADR 0025).
- The default database password is a local development value; set your own in `.env`.

## Résumé en français

IPHI surveille la santé d'une plateforme de données industrielle **simulée** : collecte, règles de santé explicables, incidents dédupliqués et prouvés, diagnostic optionnel. `make up` initialise les comptes locaux puis démarre PostgreSQL, les migrations et le seed, l'API, le worker et l'interface (http://127.0.0.1:8080). La plateforme simulée compte sept composants et neuf scénarios de panne reproductibles (seed, horloge de plateforme accélérable) ; ses mesures et logs sont validés, historisés dans PostgreSQL et consultables par l'API, et des règles versionnées avec hystérésis en déduisent l'état justifié de chaque composant et de la plateforme (jamais « sain » faute de données). Une panne ouvre un incident unique, dédoublonné par la base, rattaché aux évaluations et observations qui le prouvent, avec suppression des alertes en aval, résolution automatique au retour à la normale et diagnostic déterministe sans IA. Les sessions serveur et rôles viewer/engineer/admin protègent les accès ; les actions sensibles et refus sont audités. Le tableau de bord (vue d'ensemble, topologie, composants, incidents, scénarios, règles) affiche ces états et leurs preuves, mis à jour par SSE, avec un repli à 30 s signalé en cas de coupure. `make demo` rejoue les pannes principales sur un environnement propre et vérifie chaque conclusion ([guide](docs/demo.md), [étude de cas](docs/case-study.md)). Le dossier de conception (cahier des charges, architecture, backlog, design system, ADR) est dans `docs/`. Aucune connexion à une installation réelle n'existe ni n'est revendiquée.
