# rules.md — IPHI engineering rules

> Normative for all code, tests, migrations, configuration and commits in this repository.
> Precedence: explicit user request > this file > local conventions; the design dossier in `docs/` defines scope.
> Rule IDs are stable; cite them in reviews and ADRs (e.g. "violates C-03").

## 1. Domain rules (D)

| ID | Rule |
|---|---|
| D-01 | Health states are exactly `healthy`, `warning`, `critical`, `unknown` (API/DB enum values, lowercase). UI labels are Title Case. |
| D-02 | Missing, stale or insufficient evidence yields `unknown`. No code path defaults to `healthy`. |
| D-03 | `up = 0` from an active probe is `critical`; absence of any observation is `unknown` + `telemetry_loss`. Never infer "down" from silence (ADR 0003). |
| D-04 | Telemetry freshness and process-data freshness (`data_age_s`) are distinct failure classes and are never merged. |
| D-05 | Platform aggregation follows the priority table of ADR 0004. No averaging, no weighted scores that can mask a `critical` high/medium component. |
| D-06 | Impact (`impacted_by`) is an annotation, never a state change of the impacted component. |
| D-07 | Every state, incident and diagnostic is traceable to stored rule evaluations and observations. A value displayed without a retrievable source is a defect. |
| D-08 | Health rules are immutable versions. Changing a threshold creates a new version; evaluations keep the version they used. |
| D-09 | Hysteresis is mandatory for every rule (`raise_after`, `clear_after`, distinct clear thresholds). A rule without it is rejected at load. |
| D-10 | At most one active incident per fingerprint, enforced by the database (partial unique index), not only by code. |
| D-11 | Incident transitions go through the single state-machine module; no direct `status` assignment elsewhere. Every transition writes an `incident_event` in the same transaction. |
| D-12 | Evidence and incident events are append-only. No delete, no update of evidence content. |
| D-13 | Business timestamps come from `PlatformClock`. `datetime.now()`, `time.time()` and `Date.now()` are forbidden in domain code. All datetimes are timezone-aware UTC. |
| D-14 | `observed_at` (event time) and `received_at` (ingestion time) are both stored; ordering and windows use `observed_at`. |
| D-15 | Every metric has a declared unit and range in `metric_definition`. Values are stored in canonical units (ms, s, %, count); conversion happens at the edge. |
| D-16 | Measurement quality (`good`/`uncertain`/`bad`, mapped from OPC UA status semantics) is preserved end to end; `bad` samples never satisfy a rule as healthy evidence. |
| D-17 | Simulated data carries `source=simulation` and `scenario_run_id` and is labelled as simulated in UI, API, exports and logs. |
| D-18 | Read-only toward OT: no write, command, restart or remediation toward any monitored system, simulated or real. |
| D-19 | The LLM is never a health authority. Its output cannot change a state, open/close an incident or trigger an action. |
| D-20 | "Correlated with" is the default wording; "caused by" requires explicit causal evidence and is never produced by the LLM path. |

## 2. Reference standards (S)

Used as **design references**. IPHI claims no certification or compliance with any of them.

| ID | Standard | What we take from it |
|---|---|---|
| S-01 | ISA-95 / IEC 62264 | Vocabulary for levels (L1 control → L3 operations); component `type` and the simulated topology follow the level-2/3 data path. |
| S-02 | ISA-101 (HMI) | Grey-scale chrome, color reserved for abnormal states, consistent status shapes (see `docs/04-design-system.md`). |
| S-03 | ISA-18.2 / IEC 62682 (alarm management) | Each rule has rationale and recommendation (alarm rationalization); hysteresis/deadband against chattering; deduplication and downstream suppression against alarm floods; acknowledgement semantics. |
| S-04 | IEC 62443 | Zones and conduits mindset: IPHI is a read-only consumer; no inbound path to OT; least privilege; future connectors require a documented conduit. |
| S-05 | OPC UA status codes | `quality` mapping Good / Uncertain / Bad. |
| S-06 | RFC 3339 / ISO 8601 | Wire format `YYYY-MM-DDTHH:MM:SS(.fff)Z`. |
| S-07 | RFC 9457 | Error bodies (`application/problem+json`) with machine-readable `code` and `correlation_id`. |
| S-08 | OpenAPI 3.1 | API contract generated from code; TS client generated from it. |
| S-09 | OWASP ASVS 4 (L2 target), OWASP Top 10, OWASP API Security Top 10 | Security requirements checklist for US-11 and reviews. |
| S-10 | OWASP Top 10 for LLM Applications | Prompt injection, insecure output handling, excessive agency, sensitive data disclosure (US-08). |
| S-11 | WCAG 2.2 AA | Contrast, keyboard, focus, non-color cues. |
| S-12 | Conventional Commits 1.0, SemVer 2.0 | Commit messages and release versions. |
| S-13 | Twelve-Factor App (config, logs, processes) | Config via environment, logs as event streams to stdout, stateless processes. |

## 3. Architecture rules (A)

| ID | Rule |
|---|---|
| A-01 | Modular monolith. Modules: `core`, `topology`, `simulation`, `connectors`, `ingestion`, `health`, `incidents`, `diagnostics`, `reporting`, `identity`, `monitor`, `api` (`topology`, `monitor`: ADR 0013). |
| A-02 | Each module is layered: `domain` (pure logic, no I/O) → `service` (use cases, transactions) → `repository` (persistence) ; `api` routers only call services. |
| A-03 | Dependency direction is inward: `domain` imports nothing from `api`, SQLAlchemy, FastAPI or httpx. Enforced by an import-linter contract in CI. |
| A-04 | Cross-module calls go through a module's public service interface, never its repositories or ORM models. |
| A-05 | ORM models never leave the repository layer; services exchange domain objects; routers exchange Pydantic schemas. |
| A-06 | External systems (connectors, LLM providers, clock) are reached through ports (`Protocol`) with adapters; tests use fakes, not mocks of internals. |
| A-07 | No new top-level dependency, process, container or protocol without an ADR. |
| A-08 | Frontend: `app/` (shell, routing, providers), `features/<name>/` (screens + hooks), `shared/` (ui primitives, status components, api client, formatting). Features do not import each other. |
| A-09 | No health or incident logic in the frontend; it renders what the API computes and justifies. |

## 4. Design patterns (P)

Use these where named; do not introduce others speculatively.

| ID | Pattern | Where |
|---|---|---|
| P-01 | Ports & Adapters | `Connector`, `LlmProvider`, `PlatformClock`, `ReportRenderer`. |
| P-02 | Strategy + registry | Rule evaluators keyed by `rule_type`; scenario generators keyed by `scenario_key`; connectors keyed by `connector_key`. Registration is explicit (no import-time magic). |
| P-03 | Explicit state machine | Incident lifecycle: a transition table `(state, event) → state`; illegal transitions raise `IllegalTransition`. |
| P-04 | Repository + Unit of Work | One SQLAlchemy session per request / per `run_cycle`; commit in the service layer only. |
| P-05 | Value objects | `Fingerprint`, `MetricKey`, `TimeWindow`, `EvidenceRef`: frozen dataclasses with validation in `__post_init__`. |
| P-06 | Domain events → `NOTIFY` | Emitted inside the transaction (PostgreSQL delivers `NOTIFY` on commit), so no event escapes a rolled-back change. |
| P-07 | Pure functional core | Generator, rule evaluation, aggregation, fingerprinting and diagnosis assembly are pure functions of their inputs. |
| P-08 | Dependency injection | Constructor injection in services; FastAPI `Depends` only at the router edge. No service locator, no global mutable singletons. |

Anti-patterns rejected in review: god services, generic `BaseRepository[T]` hierarchies, deep inheritance, boolean flag parameters that switch behavior, premature abstraction (wait for the third use), stringly-typed states (use `StrEnum`).

## 5. Code quality (C)

### Common
| ID | Rule |
|---|---|
| C-01 | Names state intent in domain vocabulary (`open_incident`, `evaluate_rule`), not mechanics (`process_data`, `handle`). |
| C-02 | Functions do one thing; target ≤ 40 lines, ≤ 4 parameters (group into a value object beyond). |
| C-03 | No dead code, no commented-out code, no unused parameters, no speculative options. |
| C-04 | No magic numbers in logic: thresholds and windows come from configuration or named constants. |
| C-05 | Fail fast on invalid input at the boundary; inside the core, invariants are guaranteed by types. |
| C-06 | Errors are explicit domain exceptions mapped once to RFC 9457 responses; never swallowed. |
| C-07 | Every query that can grow is bounded (limit, window, pagination). |

### Python
| ID | Rule |
|---|---|
| C-10 | Python 3.12+, full type hints, `mypy --strict` clean; `Any` only at untyped third-party boundaries with a narrow cast. |
| C-11 | Ruff lint + format are authoritative; no per-file ignores without justification in `pyproject.toml`. |
| C-12 | Domain objects: `@dataclass(frozen=True, slots=True)`; Pydantic models only for API schemas and settings. |
| C-13 | Enumerations: `StrEnum`. Datetimes: `datetime` with `tzinfo=UTC` only; naive datetimes rejected. |
| C-14 | No bare `except`, no `except Exception` except at process boundaries (cycle loop, request middleware) where it logs with context and preserves failure semantics. |
| C-15 | Logging via `structlog` key/value events (`log.info("incident.opened", incident_id=..., fingerprint=...)`); no `print`, no f-strings as event names, no secrets. |
| C-16 | SQLAlchemy 2.0 style (`select()`), parameters always bound; no SQL string concatenation; eager loading chosen explicitly to avoid N+1. |
| C-17 | Alembic: one migration per schema change, reversible `downgrade`, never edit an applied migration; constraints and indexes declared in the migration. |
| C-18 | No mutable default arguments; no module-level mutable state. |

### TypeScript / React
| ID | Rule |
|---|---|
| C-20 | `strict` TS, `noUncheckedIndexedAccess`; no `any`, no `as` casts on API data, no `!` non-null assertions without a guard. |
| C-21 | API types come only from the generated OpenAPI client; no hand-written duplicates of backend schemas. |
| C-22 | Server state via TanStack Query; local UI state via React state; no global store unless an ADR justifies it. |
| C-23 | Components ≤ ~200 lines; split by responsibility. Every data view handles loading, empty, error and stale states. |
| C-24 | Styling only through design tokens and Tailwind utilities; no hard-coded colors, no inline style objects for theming. |
| C-25 | Dates and numbers through `Intl` helpers in `shared/format`; units always rendered. |
| C-26 | Accessibility per `docs/04-design-system.md` §9; axe must report no serious/critical violation. |

## 6. Comments and documentation (K)

| ID | Rule |
|---|---|
| K-01 | Code is self-explanatory through names and structure. Comments explain **why** (constraint, trade-off, non-obvious invariant), never **what** the next line does. |
| K-02 | No tutorial or narrative tone ("Here we…", "Now we…", "Let's…", "This function will…"). Write as a senior engineer to a peer. |
| K-03 | No banner, separator or decorative comments; no section headers inside functions. |
| K-04 | Docstrings only on public module interfaces whose contract is not obvious from the signature (units, ordering, idempotency, raised errors). One line when possible. |
| K-05 | Reference the decision when code encodes one: `# ADR 0005: reopen window measured in platform time`. |
| K-06 | No `TODO`/`FIXME` without a story or issue reference (`# TODO(US-07): …`); none may remain at story completion unless listed in the report. |
| K-07 | No comments that restate types, parameters or return values. No AI/tooling mentions in code, comments or docs. |

```python
# Bad
# Loop over samples and check if value is greater than threshold
for s in samples:
    if s.value > rule.critical_threshold:  # compare value

# Good
# Bad-quality samples cannot prove health (D-16), but they still count as observations for R-TEL-001.
usable = [s for s in samples if s.quality is not Quality.BAD]
```

## 7. Security (X)

| ID | Rule |
|---|---|
| X-01 | No secret, token, password or real `.env` in Git, fixtures, logs, screenshots or test snapshots; `.env.example` holds placeholders only; gitleaks runs in CI. |
| X-02 | Deny by default: every mutating route declares its required role; authorization is enforced server-side and tested negatively. |
| X-03 | All external input is validated by Pydantic with bounds (length, range, enum, pagination limits, time windows ≤ 7 days, body ≤ 64 KB). |
| X-04 | No user-controlled URLs, hostnames or file paths. Connector endpoints come from server configuration only (SSRF, path traversal). |
| X-05 | No `pickle`, `eval`, `exec`, `yaml.load` (use `yaml.safe_load`), `subprocess`/`os.system` in application code. |
| X-06 | Errors returned to clients never include stack traces, SQL, file paths or internal hostnames; details go to logs with the `correlation_id`. |
| X-07 | Logs and persisted prompts are redacted (credentials, tokens, emails, IPs) before writing. |
| X-08 | CSV cells starting with `= + - @ \t \r` are neutralized; HTML/PDF templates auto-escape; no `dangerouslySetInnerHTML`. |
| X-09 | LLM: logs and observations are untrusted data inside explicit delimiters; no tools exposed to the model; output schema-validated; evidence IDs verified; timeouts and token caps enforced (ADR 0006). |
| X-10 | Sessions: `HttpOnly`, `SameSite=Strict`, `Secure` outside dev; Argon2id; CSRF token on mutations; rate limit on login and LLM diagnosis. |
| X-11 | HTTP security headers (CSP without `unsafe-inline` scripts, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`); CORS restricted to the frontend origin. |
| X-12 | Containers run as non-root, minimal base images, no dev tools in runtime images; ports bound to `127.0.0.1` in development. |
| X-13 | Dependencies pinned via lockfiles; `pip-audit` and `pnpm audit` in CI; a new dependency needs a maintained project and a compatible license. |
| X-14 | Sensitive mutations (scenario start/stop/reset, ack, resolve, diagnose, auth events) produce an `audit_event`, including denied attempts. |

## 8. Testing (T)

| ID | Rule |
|---|---|
| T-01 | Domain logic is unit-tested with table-driven/parametrized tests; hysteresis and aggregation also with Hypothesis property tests. |
| T-02 | Integration tests run against real PostgreSQL (container); no SQLite substitute. |
| T-03 | Tests are deterministic: `manual` clock, fixed seed, no `sleep`, no wall-clock assertions, no network beyond the compose services. |
| T-04 | Each scenario of the catalog (architecture §05.6) has an integration test asserting states and incidents; mandatory scenarios of `docs/03-backlog.md` §01.1 have e2e coverage. |
| T-05 | Each bug fix ships with a regression test that fails before the fix. |
| T-06 | Test names describe behavior: `test_collector_down_opens_single_availability_incident`. Arrange / Act / Assert structure, one behavior per test. |
| T-07 | Coverage targets: domain modules ≥ 90 % lines, backend overall ≥ 80 %. Coverage is a signal, not a goal; no tests written only to raise it. |
| T-08 | Security negative tests for every role × mutating route once US-11 lands. |

## 9. Git, commits and attribution (G)

| ID | Rule |
|---|---|
| G-01 | Conventional Commits: `type(scope): imperative summary` in English, ≤ 72 chars; scope = module (`feat(health): add hysteresis to threshold rules`). |
| G-02 | Body explains why when non-obvious and ends with `Refs: US-XX`. One coherent change per commit. |
| G-03 | Author and committer are always the repository owner's own git identity; no co-author trailer or third-party attribution in commits, PR titles/descriptions, tags or release notes. |
| G-04 | Branches: `main` protected; work on `feat/us-XX-short-name`, `fix/…`, `docs/…`, `chore/…`. No force-push to `main`. |
| G-05 | Commit or push only when the user asks. Never commit generated build output; lockfiles and the generated API client are committed. |
| G-06 | CI must be green before merge; failures are reported, never bypassed (`--no-verify` forbidden). |

## 10. Done checklist

Before reporting a task as done: rules D/A/C/K/X respected · tests added and green · `make check` green · migrations up/down verified when touched · no secret, no stray TODO · docs/ADR updated when a decision changed · UI checked against `docs/04-design-system.md` and axe when touched.
