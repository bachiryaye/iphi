# MQTT simulation

US-12 transports the existing deterministic simulation through a **real Mosquitto broker**.
The publisher, monitored components and observations remain synthetic. This demonstrates an
MQTT adapter for IPHI's versioned JSON contract; it does not establish compatibility with a
PLC, AVEVA PI, Sparkplug B or another industrial product.

## Start and demonstrate

Docker, Compose, Make and Python 3.10+ are required, as for the regular stack.

```sh
make mqtt-up                    # isolated iphi-mqtt project, volume retained between runs
make mqtt-demo                  # same executable acceptance walkthrough through MQTT
make mqtt-down                  # stop this project; retain its database volume
```

Open http://127.0.0.1:8082 and sign in with the local accounts initialized by `make init-env`.
The API is at http://127.0.0.1:8002/docs; PostgreSQL is on loopback port 5435. Credentials stay
in the ignored local `.env`; the broker has **no published port**. The usual `iphi` and
`iphi-demo` projects have separate databases/ports. Do not run competing builds of the shared
local image while another demo is in progress.

If a port is occupied, override `IPHI_MQTT_FRONTEND_PORT`, `IPHI_MQTT_API_PORT` or
`IPHI_MQTT_DB_PORT` on every command for this project, for example:
`make mqtt-up IPHI_MQTT_DB_PORT=5438`. Existing services on those ports are never stopped.

In **Scenarios**, start `collector_down`. In **Overview**, collector-01 becomes Critical.
In **Incidents**, open its single availability incident: the rule evaluations cite stored
MQTT `up=0` samples, with source `mqtt` and the scenario UUID. Stop the scenario to observe
stable recovery and automatic resolution. Metric charts, evidence links, deterministic
diagnosis, exports and SSE use their existing API paths. All keep the simulated label.

The exact Compose invocation behind these targets is:

```sh
IPHI_FRONTEND_PORT=8082 IPHI_API_PORT=8002 IPHI_DB_PORT=5435 \
  docker compose -p iphi-mqtt -f compose.yaml -f compose.mqtt.yaml --profile mqtt up --build -d
```

Use both files: the `mqtt` profile adds the broker/publisher; the override selects MQTT
consistently for the API monitor and worker. Default `make up` continues using direct
simulation. Switching transport on an existing database requires an admin simulation reset
so old cursors and observations cannot mix with the new transport. Incident evidence stays.

## Wire contract (version 1)

The platform is fixed to `sim-plant-01`; component names must match the seeded topology.
Endpoints are configured by the server only: `IPHI_MQTT_HOST` allows the Compose name
`mosquitto` or loopback, `IPHI_MQTT_PORT` defaults to 1883, and `IPHI_MQTT_TIMEOUT_S` to 3.
The broker is anonymous/plaintext on an internal local simulation network. Real endpoints,
production access, broker bridges and OT writes are outside this adapter's scope.

| Topic | Producer → consumer | Payload |
|---|---|---|
| `iphi/sim-plant-01/simulation/collect` | Worker → simulated publisher | Request UUID, baseline UUID, `now`, `resume_after`, `not_before` |
| `iphi/sim-plant-01/<component>/metrics` | Publisher → worker | Numbered packet of metric rows |
| `iphi/sim-plant-01/<component>/logs` | Publisher → worker | Numbered packet of log rows |
| `iphi/sim-plant-01/batches/<request UUID>` | Publisher → worker | Complete packet/sample/log counts, watermark, source issues |

Every envelope explicitly includes `version: 1`, `environment: "simulation"`, `source: "mqtt"`,
`request_id` and `baseline_id`. The request UUID correlates a single collection attempt;
the baseline UUID identifies the current seed/reset epoch. Example metric packet (UUIDs and
time are illustrative; the running publisher reads them from the database):

```json
{
  "version": 1,
  "environment": "simulation",
  "source": "mqtt",
  "request_id": "00000000-0000-4000-8000-000000000001",
  "baseline_id": "00000000-0000-4000-8000-000000000002",
  "kind": "metrics",
  "sequence": 0,
  "component": "collector-01",
  "rows": [{
    "metric_name": "up",
    "value": 0.0,
    "unit": "bool",
    "quality": "good",
    "observed_at": "2026-11-19T12:00:00Z",
    "scenario_run_id": "00000000-0000-4000-8000-000000000003"
  }]
}
```

Log rows contain `severity`, `message`, scalar `attributes`, `observed_at` and
`scenario_run_id`. Completion contains `kind: "complete"`, `packets`, `samples`, `logs`,
`watermark` and `issues`. Sequence numbers start at zero across both data topics; the
manifest counts every unique packet and observation. Labels, topics and IDs are validated,
extra fields refused, timestamps timezone-aware, values finite, and payloads limited to
64 KiB / 100 rows. A batch is limited to 256 packets / 6,000 samples / 2,000 logs, within
the ingestion ten-minute lookback. Existing ingestion still validates units, catalog ranges,
lateness, observation identity and database references.

## Failure, retry and reset behavior

QoS 1 and clean sessions are used in both directions. Retained messages are disabled and
rejected. Identical packet redelivery is ignored; conflicting redelivery or counts fail the
batch. **Only a complete correlated batch** reaches ingestion. Database constraints handle
observation redelivery. This is not an exactly-once or durable message delivery guarantee.

The worker subscribes before requesting observations. Its existing shared clock lock prevents
scenario/reset changes during a collection. A deadline, three seconds by default, bounds the
exchange. Failure stores a failed `collection_run`, without partial observations. Advancing
the attempted cursor records the loss and lets the unchanged absence rule show `Unknown`
and telemetry-loss incidents; silence never becomes fabricated `up=0`. The next cycle makes
a fresh connection; the publisher reconnects with a 1–10 second backoff.

To inspect this behavior on the dedicated project:

```sh
docker compose -p iphi-mqtt -f compose.yaml -f compose.mqtt.yaml --profile mqtt stop mqtt-publisher
# Collection becomes failed/degraded; missing evidence becomes Unknown.
docker compose -p iphi-mqtt -f compose.yaml -f compose.mqtt.yaml --profile mqtt start mqtt-publisher
# Fresh observations resume; clear_after windows govern recovery.
```

An admin reset closes active incidents, clears both transports' cursors and uncited synthetic
history, and preserves evidence. Old requests/replies cannot match the new baseline/request
IDs. Lost intervals are visible gaps, not backfilled successes. A long ten-minute catch-up
or overloaded host can exhaust the deadline; no sub-500 ms cycle claim applies to timeout
or catch-up behavior. Increase the configured deadline up to 10 seconds for local diagnosis.

## Verification

```sh
make test-mqtt                   # contract tests + real Mosquitto/PostgreSQL integration
make check                      # includes MQTT tests, Docker required
```

Tests create their own disposable broker on a free loopback port and fresh PostgreSQL
databases. Docker lifecycle waits are restricted to the transport boundary; business time is
manual and the seed fixed. Integration checks collector outage/evidence/API, lost publication
and recovery, reset/evidence holds and broker reconnection. See [ADR 0026](adr/0026-mqtt-simulation-transport.md)
for the design trade-offs and [demo guide](demo.md) for the shared walkthrough.

PR #14 CI run 44538711480 completed all six jobs successfully: 692 backend tests (including
the four real-broker integration tests), 102 frontend tests, the standard demo (110 s),
12 browser regressions and the separate fake-provider test. The MQTT walkthrough passed
in 114 s; the MQTT dashboard/evidence browser test passed in 24.4 s. The final strict-version
regressions also pass locally (27 MQTT contract tests). Host startup/teardown limitations are
recorded in [performance notes](performance.md#us-12-local-transport-validation).
