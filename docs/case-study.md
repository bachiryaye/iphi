# Case study — monitoring the platform that carries the process data

IPHI (Industrial Platform Health Intelligence) is a personal project: a monitoring and diagnostics application for an industrial **data platform**. It runs entirely on a simulated infrastructure. This page explains the problem it addresses, the decisions that shaped it, what they cost, and where it stops.

[Recorded demonstration: three minutes, French explanations](media/iphi-demo-fr.mp4) · [Transcript and chapter guide](video-demo.md)

## The problem

A plant's process data travels through a chain: field sources, an edge gateway, a collector, a historian and its database, then the APIs and analytics that consume it. When a trend goes flat on a screen, the first question is not about the process. It is whether the value is true or whether the chain broke: a collector that stopped, a gateway that answers slowly, a historian that is up but serves old data, a component nobody hears from any more.

Generic infrastructure monitoring answers part of this (is the service up, how loaded is it). It tends to miss what matters to a data engineer in this setting:

- **Freshness is not availability.** A historian can answer every probe while its newest value is ten minutes old.
- **Silence is not health.** A dashboard that keeps showing the last known green state after its own collection stopped is worse than no dashboard.
- **One fault, many symptoms.** A collector outage makes everything downstream look broken; an operator needs one incident with its impact, not five alarms.
- **A conclusion needs its evidence.** "Critical" is only actionable with the rule, the window, the threshold and the samples behind it.

IPHI is built around those four points.

## What it does

A worker collects metrics and logs from seven simulated components every 5 seconds, validates and stores them in PostgreSQL, evaluates nine versioned health rules, and maintains incidents. A FastAPI service exposes the results; a React dashboard shows them. Nine scenarios (outage, latency ramp, stale data, intermittent loss, error burst, resource pressure, backlog growth, telemetry blackout, plus the nominal baseline) can be started from the interface or the API, and the outcome of each is announced in advance and tested.

`make demo` replays the main ones on a clean environment and checks every conclusion ([demo guide](demo.md)).

## Decisions and what they cost

### 1. Four states, and `Unknown` is one of them

States are `Healthy`, `Warning`, `Critical`, `Unknown`. A rule with no sample in its window is `Unknown`; a component IPHI no longer observes is `Unknown`; if the worker itself stops evaluating, the API reports `Unknown` with `stale: true` instead of the last computed state, and `/ready` fails.

*Cost:* `Unknown` has to be carried through every layer: the hysteresis (where does it sit in the severity order?), the aggregation (a high-criticality component `Unknown` makes the platform `Unknown`, not `Warning`), incidents (a silent component opens a telemetry-loss incident) and every screen. It would have been much less code to default to the last value.

### 2. The platform state is a priority table, not an average

One `Critical` collector among six healthy components is not "86 % healthy". The platform state follows an ordered table that depends on component criticality, and the API returns the line that applied ("Priority 1: a high- or medium-criticality component is Critical (collector-01)").

*Cost:* no single score to plot over time. That is deliberate: a score invites the question "is 86 good?", the rationale answers "what is wrong and where".

### 3. Rules evaluate per slot of platform time, with hysteresis

Each rule has warning and critical thresholds with separate clear levels, and needs a number of consecutive evaluations to worsen or recover. Evaluation happens once per 5 s sample slot of **platform time**, a clock that can run in real time, accelerated or step by step. The state history is therefore identical at any speed, which is what makes a two-minute demonstration and deterministic tests honest: they reach the conclusions a realtime run reaches.

*Cost:* a clock abstraction in every time-dependent path, and the discipline of never reading the wall clock in business code (enforced by a test). An observation that arrives after its slot was evaluated does not trigger a re-evaluation; that limit is documented rather than hidden.

### 4. An incident is a fingerprint guaranteed by the database

An incident is identified by platform, component and failure class. A partial unique index allows one active incident per fingerprint, so repeated observations of the same fault update it (occurrence count, severity up or down) whatever the application code does. Downstream alerts caused by an unreachable upstream component are attached to the upstream incident as impact. The same failure within fifteen minutes reopens the incident instead of opening a new one.

*Cost:* suppression can hide a second, independent fault downstream; its evidence stays attached to the upstream incident, but it does not get its own. The alternative, one incident per symptom, is the alarm storm the project set out to avoid.

### 5. Evidence is stored, linked and kept

Every state cites a stored rule evaluation: rule version, window, threshold, observed value, sample IDs. Every incident links the evaluations, samples and logs that justify it; these rows survive retention and reset. The timeline is append-only, enforced by database triggers.

*Cost:* more tables, more foreign keys, a slower purge (it must skip held evidence). Measured, not assumed: see [performance](performance.md).

### 6. Diagnosis without AI first

The deterministic diagnosis walks the dependency graph and the incident's evidence: observed facts, one hypothesis (the most upstream component in fault, worded as a correlation, never as a proven cause), and the checks recommended by the rules involved. Each claim cites evidence IDs that are validated against the incident's evidence set. The implemented optional AI diagnosis uses bounded, redacted evidence and validates the provider's output and citations. If the provider is unavailable or its answer is rejected, the deterministic path remains available: the full demonstration runs with no provider configured ([diagnosis guide](diagnosis.md)).

*Cost:* the deterministic text is plain and limited to versioned rule recommendations and stored observations. It is reproducible and needs no external provider. Citations establish traceability, not factual truth.

### 7. A modular monolith with one scheduler

One PostgreSQL, one API process, one worker holding an advisory lock, one Compose file. Module boundaries (simulation, connectors, ingestion, health, incidents, diagnostics) are checked by import contracts in CI. The default simulation requires no broker; the optional MQTT transport adds Mosquitto. No separate time-series database or microservice architecture is needed.

*Cost:* it does not scale horizontally as is. For seven components and a week of history it does not need to, and the measured numbers say so. The connector port also carries the [MQTT simulation](mqtt.md): a real Mosquitto broker and separate synthetic publisher feed the same ingestion and health engine. This validates a transport boundary, not a real industrial source.

### 8. The simulator never knows the thresholds

Fault effects are pure functions of the nominal reading, the seed and the elapsed time. They do not read the health rules. The expected outcome of each scenario is documentation checked by tests, not a value the simulator arranges.

*Cost:* some scenarios need tuning when a rule changes, and that is the point: a test that fails when the rule and the fault disagree is a real test.

### 9. An interface for reading states, not for decoration

The dashboard follows a written design system inspired by high-performance HMI practice (ISA-101): neutral greys, colour reserved for abnormal states and never used alone (shape and text carry the state too), values shown against their thresholds, UTC everywhere with the local time alongside, no animation that is not data. Every screen has loading, empty, error and stale states, and is checked with axe in the test suite.

*Cost:* it looks quieter than a marketing dashboard. An operator looking for the one abnormal thing benefits from that.

## How it is verified

- Backend: unit tests for the pure domain (generator, rules, hysteresis with property-based tests, aggregation, incident engine), integration tests on a real PostgreSQL for every scenario of the catalog, migrations and the API. Coverage is reported by CI, not claimed here.
- Frontend: component and screen tests with accessibility checks.
- End to end: Playwright against the Compose stack for the mandatory scenarios; `make demo` as an executable acceptance test of the API path.
- Contract: the TypeScript client is generated from the OpenAPI document; CI fails on drift.
- Supply chain and secrets: dependency audits and a secret scan of the full history in CI.

## Limits

- **Industrial observations are simulated.** The optional MQTT adapter uses a real local broker carrying synthetic observations; no plant, PLC or commercial historian is connected. No commercial compatibility is claimed or implied. Thresholds are demonstration values, not industrial recommendations.
- **Local identity scope.** Server sessions, Argon2id, CSRF and viewer/engineer/admin roles protect the simulated platform; no public deployment or account-management interface is included.
- **SSE resynchronizes on connection**, with an explicit 30 s polling fallback and no durable event replay.
- **One platform, seven components, one worker.** Performance was measured at that size only, on a 2015 laptop with a spinning disk: every target is met except the 7-day aggregated series (p95 337 to 613 ms for a 300 ms target), whose query takes 123 ms in the database when the host is idle.
- **Detection delay is bounded by the design**, not optimised: two failed probes at 5 s plus one worker cycle, so up to about 15 s in real time.
- Simulator and late-data boundaries are described in the [architecture](02-architecture-technique.md) and [decision records](adr/README.md); measured host limits are in [performance.md](performance.md).

## Delivered portfolio scope

The optional MQTT adapter runs with a simulated publisher in an isolated Compose profile.
Its versioned, bounded JSON batches preserve event time, measurement quality and scenario
attribution; complete batches reach the existing engine, while transport loss remains missing
evidence. Live updates, evidence-grounded diagnosis with a deterministic fallback, and
PDF/CSV reports use the same stored observations. Local sessions, role checks and audit
protect the operational actions. The README, public beginner guide and contextual help
are delivered, with a persistent English/French interface. Stored messages and diagnoses
keep their original language; PDF/CSV reports remain English. The [beginner guide](getting-started.md)
and [French guide](debuter.md) explain the complete investigation journey.
No real plant connection or public deployment is included in this demonstrator.

## Résumé en français

IPHI surveille la santé d'une plateforme de données industrielle **simulée** plutôt que celle des machines. Quatre choix structurent le projet : `Unknown` est un état à part entière (le silence n'est jamais « sain ») ; l'état de la plateforme suit une table de priorités et non une moyenne ; un incident est une empreinte garantie par la base (pas de tempête d'alarmes, les symptômes en aval sont rattachés comme impact) ; chaque état et chaque incident citent les évaluations et les mesures stockées qui les justifient. Le diagnostic est d'abord déterministe et sourcé ; l'IA reste une couche optionnelle. Limites assumées : tout est simulé, identité limitée à la démonstration locale, une seule plateforme de sept composants.
