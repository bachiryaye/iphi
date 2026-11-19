# ADR 0026 — Bounded MQTT simulation batches

- **Status:** Accepted (US-12, implements ADR 0011)
- **Date:** 2026-11-19

## Context

Health evaluates each event-time slot once. Independent asynchronous publication would race
that evaluation and simulation resets. The connector must reproduce the deterministic source
without changing `health/` or `incidents/`, or infer service failure from missing telemetry.

## Decision

- Use `paho-mqtt` 2.x (EPL-2.0 / EDL-1.0) and Mosquitto 2.x. A separate process in the
  backend image reads the persisted simulated clock/scenarios through `SimulationService`.
  It generates observations only; the worker still owns collection, rules and incidents.
- Select exactly one transport, `simulation` (default) or `mqtt`. Existing incident source
  constructor injection and monitor connector keys follow that selection. Switching transports
  requires a simulation reset; retained incident evidence remains available.
- The worker subscribes before publishing a correlated request to
  `iphi/sim-plant-01/simulation/collect`. The request contains a random UUID, the active
  baseline UUID, platform time, cursor and fixed ten-minute lookback. It is a read request to
  the synthetic publisher, never a command to a monitored system.
- Replies use the ADR 0011 topics `iphi/<platform>/<component>/metrics` and `/logs`.
  Each version-1 JSON envelope carries `source=mqtt`, `environment=simulation`, request and
  baseline UUIDs, sequence and component. Observation rows retain event time, quality, unit
  and scenario UUID. A final `iphi/<platform>/batches/<request UUID>` manifest gives packet,
  sample and log counts, watermark and bounded source issues.
- QoS 1, clean sessions, no retained messages or disk persistence. A batch is accepted only
  when every sequence and count agrees; identical redelivery is harmless, conflicting
  redelivery is rejected. No partial batch is persisted. Database observation uniqueness
  remains the ingestion authority. Delivery is **not exactly once** or crash durable.
- Payloads ≤ 64 KiB, ≤ 100 rows/packet, ≤ 256 packets/batch, ≤ 6,000 samples and 2,000 logs.
  Request queue ≤ 4; publish queue ≤ 16. Strict bounded schemas reject extra fields, naive
  timestamps, nonfinite values and unexpected topics/identities. Existing ingestion validates
  metric units/ranges/time tolerances and persists rejection counts.
- A collection has a three-second transport deadline by default. Lost/invalid batches are
  visible failed `collection_run`s and advance the cursor to the attempted slot: this records
  loss and allows the unchanged absence rule to produce `Unknown` / `telemetry_loss`.
  No fake `up=0` is produced. Later cycles reconnect; the publisher retries its connection
  with bounded backoff. A failed database transaction can replay; ingestion deduplicates.
- The worker's existing shared clock lock spans the request and ingestion. The baseline UUID
  rejects old replies after reset. Reset purges both simulated transports and cursors with
  evidence holds. Only the publisher's fixed seeded platform is allowed.
- `mqtt` Compose profile adds a non-root broker and publisher. `compose.mqtt.yaml` selects
  MQTT for the worker/API together. `make mqtt-up` uses an isolated local project and ports.
  The broker has no host port and uses an internal network; anonymous plaintext access is
  limited to this local synthetic conduit. Endpoints are server configuration restricted to
  the Compose broker or loopback. Production authentication/TLS, arbitrary sources, MQTT
  bridges, Sparkplug B, OPC UA and real OT connectivity remain out of scope.

## Alternatives

- Uncoordinated push: would require delayed evaluation, replay and a new late-data policy.
- Publisher inside the worker: would obscure the transport/process boundary being demonstrated.
- Persistent MQTT sessions and post-commit acknowledgements: extra crash/outbox semantics are
  unnecessary for a reproducible simulation; loss is explicit instead.

## Consequences

The demo exercises a real broker and existing rules/dashboard, while the wire protocol remains
an IPHI simulation contract, not a generic industrial integration. A missing publisher consumes
the bounded timeout and can increase cycle duration; no sub-500 ms claim applies to that failure.
No schema migration, business rule or UI change is required (D-02/03/07/13/17, A-06/07,
X-03/04/06/12/13, T-02/04). Tests use a real disposable broker container and PostgreSQL.

References: [Paho client API](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html),
[Mosquitto configuration](https://mosquitto.org/man/mosquitto-conf-5.html).
