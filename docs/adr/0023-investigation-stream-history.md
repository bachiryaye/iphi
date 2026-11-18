# ADR 0023 — Live investigation and recorded state history (US-07)

- Status: accepted within approved US-07
- Date: 2026-11-18

## Context

US-07 requires committed updates within two seconds, a usable disconnected mode,
interactive dependencies, and investigation across recorded metrics, health and incidents.
Health remains authoritative on the server (D-01, D-02, D-06, D-08).

## Decision

Use transactional PostgreSQL NOTIFY and one asynchronous LISTEN connection per API
process. Notices carry only entity ID, type, platform UTC and simulation marker. Each
browser invalidates its active query cache, coalesced for 100 ms. Native FastAPI SSE
provides framing, cancellation, cache/proxy headers and keepalives. There is no replay
log: every connection begins with `sync`, which reloads active queries. Native retry
and a quiet-stream watchdog reconnect; browser offline closes the stream immediately,
and online creates a new connection; disconnected/unsupported clients poll every
30 seconds with an explicit banner. Monitor liveness keeps an independent five-second
poll. Admission is bounded to 32 streams/process and 64 queued notices/stream; overflow
closes the stream, forcing a full resync. No listener or renderer is a health authority.
The API bounds graceful shutdown to five seconds so persistent SSE requests cannot
prevent lifespan cleanup before the container's stop deadline.

Read state history from compact persisted rule evaluations and current rule-state
watermarks. Return complete half-open windows, explicit Unknown gaps, rule versions
and a bounded set of representative evaluation IDs. Normal unchanged evaluations are
persisted once per minute; continuity therefore ends after 65 seconds without proof.
A gap trusts only the initial five-second sample, unless the current persisted rule-state
watermark supports that interval. Reset boundaries cut continuity. Queries are bounded
to seven days, 100,000 compact evaluation rows and 2,000 display segments per lane;
overflow requests a smaller window rather than silently dropping transitions.

Aggregate the component from unbinned rule intervals using the existing domain order
Critical > Unknown > Warning > Healthy. Only subsequent **display** bins use the design
system §6.3 peak order Critical > Warning > Unknown > Healthy. `contains_unknown`
preserves any missing coverage in such a bin. Neither operation averages state or
changes the current health engine. Binned lanes explicitly identify their approximation.

Use React Flow with dagre for a fixed directed topology with pan, zoom, keyboard
selection and a details panel; retain a semantic dependency table. These maintained
React/TypeScript libraries implement the approved UI, without altering the stack.
Investigation lane/time filters are preserved in the URL and validated before querying.
Comment events reuse the append-only incident timeline and audit transaction. Mutation
policy remains ADR 0007 until US-11; comments never change incident state.

## Consequences

Restarting the API loses notices but not evidence. Resync repairs lost updates and slow
clients. A load balancer must permit SSE; each process owns its bounded connections.
Historical retained evidence alone cannot prove continuous monitoring through a gap.
Representative IDs are investigative links, not a claim to enumerate all evaluations.
No new table, industrial connector, provider call or real-time graph animation is needed.

## References and validation

- [FastAPI native SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [Psycopg asynchronous notifications](https://www.psycopg.org/psycopg3/docs/advanced/async.html#asynchronous-notifications)
- [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility)
- [React Flow layouts](https://reactflow.dev/learn/layouting/layouting)
- [Uvicorn shutdown budget](https://uvicorn.dev/settings/#timeouts)

Validation: transaction commit/rollback, actual HTTP streaming, listener reconnect and
capacity, history gaps/reset/peak preservation, comments/audit/denials, keyboard/UI
review and real browser update latency. Results are recorded with delivery evidence.
