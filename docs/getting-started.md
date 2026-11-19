# Getting started with IPHI

[Français](debuter.md) · [README](../README.md)

IPHI uses simulated equipment only. Install Git, Docker with Compose v2, GNU Make, Python 3.10+ and curl.

```sh
git clone https://github.com/bachiryaye/iphi.git
cd iphi
make demo IPHI_LLM_PROVIDER=none
```

Wait for `Demo passed in … s`, then open http://127.0.0.1:8081. The first build downloads dependencies; the walkthrough takes about two minutes after build on the reference machine and longer under disk load. Ports 8081, 8001 and 5434 must be free. Help is public at http://127.0.0.1:8081/help.

Open your private `.env` in an editor: use `IPHI_DEMO_ADMIN_PASSWORD` for `admin`, and the matching entries for `engineer`/`viewer`. Never publish those values. Choose **Français / English** before signing in; the preference survives reload.

## Start here: sign in

IPHI monitors an industrial data platform: seven simulated services move data from a source through a gateway and collector to storage and analysis. No real plant is connected. You need a local account supplied by the demo owner; there is no public registration.

**Try it :** Open Sign in, enter your username and password, then open Overview. For a local installation, run make init-env then make up from the repository; the generated accounts are in your private .env file.

**What to expect :** Overview shows seven components, a platform state and the monitor status. Viewer can inspect and export; engineer can run scenarios, change the clock, comment and manage incidents; admin can also reset the simulation and read Audit.

## Read the platform state

Healthy means the available evidence satisfies the rules. Warning and Critical mean a named rule crossed a threshold after its confirmation period. Unknown means evidence is missing, stale or insufficient; it never means Healthy. Impact is an annotation from dependencies, not a change to the component’s own state.

**Try it :** In Overview, read the explanation below the platform state. Compare it with Monitor status in the header. Open a component to find the deciding rule and evidence IDs.

**What to expect :** You can distinguish a fault in a simulated service from an IPHI collection problem. A stalled monitor is shown separately; silence cannot prove that a service is down.

## Inject a collector fault

Use an engineer or admin account. Scenarios change only the simulation. Viewer sees the catalog but cannot start or stop a run. Each card shows its technical key, target and expected result.

**Try it :** Open Scenarios. On Collector down (collector_down), keep target collector-01 and leave duration empty, then choose Start scenario once. Open Overview and wait for the rules to confirm the fault.

**What to expect :** collector-01 becomes Critical and one active availability incident appears with stored evidence. Downstream components may show impact. In realtime the detection target is 15 s; a loaded machine can take longer. Repeated samples update the same incident.

## Inspect a component and its metrics

Components lists the services; Topology shows their dependencies. Arrows follow the data from a dependency toward its dependent. A component page combines its own health, metric history, recorded rule evaluations and recent warning/error logs.

**Try it :** Open Components, then collector-01. Inspect up and probe_latency_ms and their units. Use the time-window controls or View as table; use the recorded state band to select an evaluation and follow its evidence.

**What to expect :** up = 0 is a failed active probe. A gap means no sample; it is never drawn as zero. data_age_s measures the age of process data, which differs from missing monitoring telemetry. Thresholds apply to a rule’s window aggregate, not necessarily a single plotted point.

## Investigate the incident

An incident groups repeated signals by fingerprint. It preserves its timeline, rule versions and linked observations. The states are Open, Acknowledged and Resolved. Taking responsibility does not repair the simulated service.

**Try it :** Open Incidents and the collector incident. Read Signal, Timeline and Evidence chain. Select an evidence chip to locate its sample, log or evaluation. Engineer/admin can Acknowledge and add an investigation comment; viewer can inspect all these records.

**What to expect :** The incident remains open or acknowledged while the condition persists. Evidence IDs and canonical keys stay unchanged in both interface languages. Stored messages, comments and explanations are shown in their original language.

## Use diagnosis with evidence

Diagnosis explains stored evidence; it never decides health or performs remediation. The deterministic version works without any model or network provider. The optional AI version can be disabled, unavailable or rejected.

**Try it :** With an engineer/admin account, choose Diagnose on the incident. Read Facts, Hypotheses and their uncertainty, Checks and Limitations. Follow the citations. If an optional AI provider is configured, compare its result with the deterministic reading.

**What to expect :** Every cited claim links to incident evidence, but a citation alone does not prove the claim. Correlation is not causation. Provider failure leaves monitoring and deterministic diagnosis available. Generated text remains in its original language; switching to French does not translate it.

## Stop the fault and observe recovery

Stopping a scenario restores its nominal signals. Rules require a stable recovery period (hysteresis), so the incident does not close immediately. Acknowledgement and manual resolution are different operations.

**Try it :** In Scenarios, find the collector_down run under Active scenario runs and choose Stop. Return to the incident. Keep realtime or use the accelerated clock with an engineer/admin account to shorten the wait. Do not use Reset to demonstrate normal recovery.

**What to expect :** The incident resolves automatically once its rules clear, and its evidence remains available. Connectivity uses a 300 s window, so full recovery can take about five minutes of platform time. Resolve is unavailable while the fault condition is active. Reset is an admin-only operation with a separate confirmation.

## Export the investigation

Reports use an existing snapshot of the stored incident and diagnoses. Exporting does not call a language model. All three roles can export. Files identify the simulated environment and use UTC timestamps.

**Try it :** Open the incident and choose Export PDF or Export CSV. Wait for the browser download. Review the summary, timeline, evidence register and any existing diagnosis.

**What to expect :** A file named IPHI-INC-…-simulated is downloaded. Report content stays in English and stored evidence keeps its original language. A busy renderer can be retried; an oversized report is refused explicitly rather than silently truncated.

## Vocabulary, units and time

Telemetry is the measurements and logs collected by IPHI. A probe actively checks whether a service answers. Freshness is the age of the process data (data_age_s), not the age of the monitoring response. A rule evaluation records the version, window, threshold and evidence behind a state. Debounce confirms a change over consecutive evaluations; hysteresis requires stable recovery. A fingerprint groups repeated signals into one incident.

**Try it :** Read ms as milliseconds, s as seconds, % as percent and count as a quantity. The simulated platform clock drives observations and incident history; UTC is always available and the browser’s local time is identified. Audit uses real wall-clock UTC. Refresh age describes the age of the API response.

**What to expect :** Simulation is the default source. MQTT is an optional real transport carrying synthetic observations, not proof of a real industrial integration. The language switch changes labels and number formatting while technical keys, units, API values and stored evidence remain intact.

## When something looks wrong

Unknown after startup: allow collection and evaluation to populate the windows. A stalled monitor or API error: inspect readiness and the local service logs; do not interpret an old green sample as current health. No incidents: clear filters or start a fault with an authorized role.

**Try it :** 401: sign in again. 403: check your role; admin is required for reset and Audit. 429: wait for the rate limit before retrying. AI off: use Diagnose. Export busy: retry; oversized report: use the evidence/event lists. No account: ask the demo owner or follow the repository access guide. Port busy at startup: select the alternate ports documented in the README.

**What to expect :** Retry keeps the failure visible and displays a correlation ID when supplied by the API. The technical server message is preserved in its original language. Local disk pressure can delay startup, collection and tests; see docs/performance.md for the measured limits.

## Tests and stopping

The [README](../README.md#tests-and-development) lists development prerequisites and exact commands. `make lint typecheck`, `make test-frontend` and `make test-e2e` check static quality, components and real journeys.

```sh
docker compose -p iphi-demo stop
# Keep demo data / retain its volume
make demo-down
# Delete the demo AND its volume
```

**`make demo` also recreates the demo volume on every run.** Development data is separate. Use `make up IPHI_LLM_PROVIDER=none` (UI 8080) and `make down` for persistent development history. See [access and roles](access.md), [MQTT](mqtt.md), [performance and limits](performance.md).
