# Measured performance

Targets of the architecture §07.2, measured with `make perf` (`backend/scripts/perf.py`) and the Playwright first-display test, on the demo stack built from the current images. Every figure below was observed; none is extrapolated.

## Machine

| Item | Value |
|---|---|
| CPU | Intel Core i5-6300U (2 cores, 4 threads, 2.4 GHz, 2015 laptop) |
| Memory | 7.6 GiB, swap in use during the runs |
| Disk | 5,400 rpm SATA hard disk (Toshiba MK6459GSXP), ext4 |
| Load | the owner's desktop session (browser) ran during every measure; I/O pressure (`/proc/pressure/io`, `some` over 300 s) between 40 % and 70 % |
| Stack | Docker Compose project `iphi-demo`, PostgreSQL 16 with its default configuration (`shared_buffers` 128 MB, `synchronous_commit` on) |

This is a slow host. Commit latency dominates: a single PostgreSQL `COMMIT` took up to 7 s during ordinary cycles and 126 s once, during a checkpoint (ADR 0019).

## Method

- **API latency**: 5 warm-up requests, then 200 sequential requests from inside the API container, nearest-rank p95. `GET /metrics` is measured on `historian-01` `probe_latency_ms`, over the last 2.8 h (2,000 raw points) and over 7 days (2,000 buckets).
- **Worker cycle**: duration published by the worker heartbeat, 36 consecutive cycles on the realtime clock.
- **Detection delay**: `collector_down` started on a Healthy platform, time until `collector-01` reads `Critical` through the API, polled every 0.2 s; three injections.
- **First display**: five cold loads of the Overview in fresh browser contexts, from navigation to the `collector-01` row being visible (production build behind Nginx).
- **7 days of history**: `--history-days 7` first stores 4.7 M nominal samples produced by the simulator's generator, dated before the stack's history and labelled `simulation`, then runs `VACUUM (ANALYZE)`.

## Results

### Short history (0.2 day, 145 k samples)

Run on 2026-11-16, fresh stack, right after the README captures.

| Indicator | Observed | Target | Met |
|---|---|---|---|
| `GET /incidents` (50 newest) | p50 19 ms, p95 28 ms, max 38 ms | p95 < 300 ms | yes |
| `GET /metrics`, 2.8 h, 2,000 raw points | p50 54 ms, p95 95 ms, max 157 ms | p95 < 300 ms | yes |
| Worker cycle | p50 209 ms, p95 288 ms, max 336 ms | p95 < 500 ms | yes |
| Detection delay, `collector_down` | 8.5 s, 9.2 s, 14.2 s | ≤ 15 s | yes |

### Seven days of history (4.7 M samples, table and indexes 1.48 GB)

Two runs on the same stack, 2026-11-16: the first right after the backfill, the second 15 minutes later without a new backfill.

| Indicator | Run 1 | Run 2 | Target | Met |
|---|---|---|---|---|
| `GET /incidents` (50 newest), p95 | 20 ms | 43 ms | < 300 ms | yes |
| `GET /metrics`, 2.8 h raw, p95 | 38 ms ¹ | 67 ms ¹ | < 300 ms | yes |
| `GET /metrics`, 7 days aggregated, p95 | 337 ms (p50 206, max 1,297) | 613 ms (p50 293, max 891) | < 300 ms | **no** |
| Worker cycle, p95 | 1,533 ms (p50 310, max 4,949) | 388 ms (p50 202, max 480) | < 500 ms | run 2 only |
| Detection delay, `collector_down`, max | 14.8 s | 14.9 s | ≤ 15 s | yes |

¹ These two runs returned 563 and 609 raw points instead of 2,000: the backfill was anchored on the oldest stored sample, which was an incident evidence sample kept across resets, leaving a gap before the current history. The script now anchors on the start of the active baseline run; the short-history run above returned 2,000 points.

### First display

| Run | Five cold loads | Target | Met |
|---|---|---|---|
| `make test-e2e`, after `make demo` | 1,061, 418, 483, 417, 332 ms | < 2 s each | yes |

### Migration 0006

Rebuilding the covering unique index on `metric_sample` took 109 s on 4.3 M samples, under a write lock: the worker waits for `migrate` to finish.

### Authenticated dashboard (US-11, 2026-11-19)

The same first-display test now starts with a real server session and an empty browser
cache for each load. The performance assertion remains below 2 seconds for every load.

| Environment | Five cold loads (ms) | Target met |
|---|---|---|
| Local, loaded host, run 1 | 2486, 2015, 1045, 1882, 879 | no |
| Local, loaded host, run 2 | 1833, 1239, 2052, 911, 821 | no |
| PR #12 CI, run 44483207714 | 272, 250, 254, 237, 245 | yes |

Local I/O pressure reached 93%; PDF and worker-cycle waits also timed out in some
browser scenarios. The first local suite finished with 9 passed, 3 failed and one
optional skip; the second with 7 passed, 5 failed and one skip. The viewer-context
and redirect waits were corrected separately; its final isolated local test passed.
CI completed all 12 browser tests and the separate fake-provider test. These are
different environments, not a before/after performance comparison. The historical
7-day series target miss above remains unresolved.
An additional isolated local first-display attempt also timed out before completing
its five loads while I/O pressure reached 99%; it provides no successful timing sample.

## US-12 local transport validation

The initial MQTT integration setup could not create its disposable broker within 120 s on
this loaded host. A later run passed collector outage/evidence/API, publisher loss/recovery
and reset/evidence holds; a separate broker-restart testcase passed but Docker removal
exceeded the 120 s teardown limit, leaving that pytest invocation with an error. The owned
container was subsequently confirmed removed. These are not reported as a green local suite.
An initial reconnect fixture used a dynamically published port; it now reserves a stable
loopback port across container restart. No business assertions or timeouts were weakened.

The local Compose build also encountered an occupied PostgreSQL port 5435 belonging to
another application. The MQTT Make targets accept independent port overrides; validation
continued on 5438 without stopping that application. I/O pressure during these attempts was
roughly 60–85%. These results do not establish a new performance baseline.

PR #14 CI run 44538711480 passed all four real-broker integration tests and the complete
MQTT walkthrough (114 s) and browser path (24.4 s), in addition to the existing regression
suite. No new seven-day load test was run; the earlier measured target misses remain.

## Reading

- The 7-day aggregated series misses its target on this host. PostgreSQL executes the query in 123 ms with every page in cache (parallel index-only scan of 120 k rows, sort, group by `date_bin`); the rest is contention with the host's I/O and CPU load, which also explains the spread between the two runs. The target is not reported as met.
- The worker cycle met its target in the second run only. The first run started right after a 4.7 M-row bulk load; cycle time on this host follows commit latency.
- Detection stays under 15 s by a small margin, by design: two failed probes at 5 s plus one cycle.
- Not measurable before US-07: event to display through SSE (< 2 s).

## Reproduce

```sh
make perf                                   # on an empty demo stack
make perf PERF_ARGS="--history-days 7"      # stores a week of samples first: about 20 min on this host
```

`make perf` exits non-zero when a target is missed. On a host with a spinning disk, stop other database containers first (`docs/demo.md`, Troubleshooting).
