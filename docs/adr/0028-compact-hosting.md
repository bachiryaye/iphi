# ADR 0028 — Compact hosting with separate API and worker

- **Status:** Accepted (owner authorization, 2026-11-21).
- **Scope:** US-01/US-10 deployment extension; no new story or domain behavior.

## Context

The owner requests a free, temporary portfolio deployment using image entrypoints.
Compose remains a local development tool. A hosted frontend container, API and
worker would occupy three service slots, while Northflank Sandbox currently offers
two services and one database. Resource availability must be checked in the actual
account; low visitor traffic does not stop background collection or memory allocation.

## Decision

- Add an optional root-context `Dockerfile.compact`. It builds the existing React
  application and copies only its compiled output into the existing Python runtime.
  The same image retains `iphi-entrypoint api`, `worker` and `migrate` (ADR 0020).
- With `IPHI_FRONTEND_DIR` configured, the API serves built assets and HTML
  navigations after all API routes. Without it, the existing local Vite/Nginx paths
  remain available. No scheduler or additional web-server process enters the API.
- Preserve separate API/worker processes, PostgreSQL locks, persistent observations,
  health rules, incidents, evidence, SSE, RBAC and diagnostics (A-01/07, D-02/07/12).
- Serve only the build's public files and recognized asset types. Missing API and
  asset paths remain structured errors. Deny dotfiles, source maps and paths escaping
  the build directory. The UI keeps the existing Nginx CSP; API responses retain
  their stricter policy and `no-store`. Hashed assets are immutable; HTML and the
  unhashed theme initializer revalidate (X-04/06/10/11).
- A root build-context allowlist excludes credentials, private instructions, browser
  sessions and generated artifacts (X-01/12). Runtime remains non-root with the same
  locked dependencies. Plain managed PostgreSQL URLs explicitly select psycopg;
  encoded credentials and TLS query parameters are preserved.
- Northflank configuration uses one public API/UI service, a private worker and
  private PostgreSQL. Secrets are restricted to runtime-tagged resources and are
  not build arguments. The existing serialized migrate-on-start option seeds users
  before either role begins work. HTTPS enables existing Secure sessions.

## Alternatives

- A separate hosted frontend consumes another service slot or requires a second
  provider and a cross-provider reverse proxy.
- Combining API and worker under a process supervisor changes failure isolation
  and conflicts with ADR 0001/0020.
- Automatic suspension based on visitors would change monitoring and clock
  semantics and cannot remove the provider's charge for reserved memory. Existing
  manual-clock operation can limit history growth between demonstrations.

## Consequences and limits

Two service slots are sufficient for the direct-simulation profile. The optional
MQTT broker and publisher still require additional infrastructure; they are not
silently merged into the worker or advertised as part of this free profile.
Retention remains seven platform days; evidence and audits keep their existing
holds. No availability, performance or month-long free-hosting guarantee follows
from packaging. Validate actual memory, CPU, storage, TLS, SSE and reports before
sharing a deployed URL. No schema migration or API contract change is needed.

References: [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/),
[Northflank pricing](https://northflank.com/pricing),
[Northflank entrypoints](https://northflank.com/docs/v1/application/run/override-command-entrypoint).
