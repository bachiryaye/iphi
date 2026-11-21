# Compact portfolio deployment

IPHI remains a simulated demonstrator. The compact profile preserves the existing
React application, API, worker, PostgreSQL history, incident evidence, roles, SSE
and reports. It changes how the interface is delivered, following [ADR 0028](adr/0028-compact-hosting.md).

| Resource | Image and role | Exposure |
|---|---|---|
| Web | `Dockerfile.compact`, default `api` | HTTPS UI and `/api/v1`, one origin |
| Worker | Same image, command `worker` | Private; no HTTP port |
| Database | PostgreSQL 16 | Private persistent addon |

`IPHI_FRONTEND_DIR=/app/frontend` is set by the compact image. The separate backend
image leaves it unset and continues to work with local Vite/Nginx. The image's
entrypoint performs `exec` for the selected role. Neither a supervisor nor the
scheduler runs inside the API process. Docker Compose is not required for hosting.

## Verify locally without Compose

With Docker, Python 3, Bash and curl installed:

```sh
make compact-check
```

This builds the image, starts a fresh private Docker network with PostgreSQL and
separate API/worker containers, migrates/seeds through the image entrypoint, checks
the compiled public interface, and runs the existing deterministic demonstration.
Each running container has a 256 MiB memory ceiling. The API port is allocated on
loopback; the database and worker have no published ports. Runtime credentials are
random and stored in a private temporary directory, never printed. Cleanup removes
only the resources created by this check, including its disposable database.

CI also runs the existing browser journeys on this compact stack, including
faults, evidence, SSE, viewer permissions, PDF/CSV and bilingual help. Browser
sessions can be isolated with `IPHI_E2E_STATE_DIR`; their default local paths
remain available for the original development stack.

For browser inspection, `IPHI_COMPACT_KEEP=1 make compact-check` retains the check's
resources and prints their prefix and private state-directory path. `url` contains
the loopback address; `runtime.env` contains the disposable account passwords.
Use a separate browser profile to avoid mixing sessions with other local stacks.
Remove these specific containers and their network when finished; never run a
global Docker prune or remove another project's volumes.

The local check uses HTTP sessions restricted to loopback. The hosted configuration
uses production mode and HTTPS; it must not be downgraded to make sign-in work.

## Northflank configuration

The [template](../deploy/northflank/template.json) is a deployment specification,
not evidence that an account has been provisioned. The current Sandbox offer
advertises two services, one database and up to $20 per month in resources, with
always-on services. Confirm the actual account permits the selected compute,
database disk, build resources and region before running it. Remain on Sandbox;
do not accept a paid upgrade or select BYOC for this free demonstration.

1. Sign in to Northflank and connect the GitHub account with access to this repository.
2. Open Templates, create a template using the code editor, and load the JSON file.
   Template name/description are entered in Northflank, outside the specification.
3. Set `branch` and **`commitSha` to the validated published revision**. The empty
   default SHA is deliberately incomplete. Set `gitAccount`, project name and
   region to the connected account's values. Run the provider's dry-run and inspect
   the resource/price preview before provisioning. The default PostgreSQL disk is
   6 GiB to allow the existing seven-day history; verify it fits the free quota.
4. The workflow creates private PostgreSQL, prepares the web service with zero
   instances, creates runtime-only secrets, builds the selected revision, starts
   the worker from that build, then starts the web service. Existing advisory locks
   serialize migration and seed when both roles start. Later deployments briefly
   stop the web instance while the pinned build is replaced; this is a demo workflow.
5. Confirm both processes run the selected build. Open the web service's generated
   HTTPS domain. The allowlist uses that exact domain and loopback addresses.
   `/health` checks API liveness; `/ready` checks database, migration and worker
   readiness. Provider liveness invokes `iphi-entrypoint healthcheck` locally, so
   worker degradation can still be explained by the accessible UI.
6. Retrieve the generated demo passwords privately from the restricted runtime
   secret group. Give reviewers only the role they need: `viewer` for inspection,
   `engineer` for fault injection. Keep `admin` private. All mutations remain
   authorized, protected by CSRF and audited.
7. Run the acceptance path on the actual HTTPS URL: sign in, inspect Overview,
   start `collector_down` as engineer, verify one incident and its evidence,
   request a deterministic diagnosis, export CSV/PDF, stop the fault and verify
   recovery. Check direct page reload, SSE updates and a viewer's denied mutation.
   Recheck access after an API restart before sharing the link with a recruiter.

The database connection is supplied by the addon's `POSTGRES_URI` secret, aliased
to `IPHI_DATABASE_URL`. Settings explicitly select psycopg while preserving its
credentials and TLS parameters. Role passwords are generated and retained by the
provider; no password or API token belongs in the JSON or Git. Secrets have
`environment` scope and runtime-tag restrictions, so they are not injected into
the frontend build. The template disables automatic builds on arbitrary pushes.

The default LLM provider is `none`; deterministic diagnosis remains available.
The optional free-only OpenRouter adapter can be configured later with a private
runtime secret. No paid-model access is implied or required.

## Resource use between visits

Visitor traffic is only one source of load. A realtime simulator still writes
observations every five seconds while no browser is open. Retention is seven
platform days, and referenced evidence is never silently deleted. The small local
check does not establish month-long storage use or cloud performance.

For a demonstration that should remain at a chosen simulated instant, use the
existing **Scenarios → Platform clock → Manual** control as engineer/admin. The
platform time and simulated samples then stop advancing until an authorized user
advances it or selects Realtime. Worker health checks and reserved container memory
remain; this does not scale the provider's services to zero. The UI shows the
clock mode, so paused simulation is explicit. Automatic visitor-based suspension
is not part of this packaging profile.

The optional MQTT simulation remains available locally. Its real broker and
separate synthetic publisher exceed this two-service layout and require their own
hosting assessment. No MQTT, industrial-plant or production availability claim is
added by publishing the direct-simulation demo.

References: [Northflank pricing](https://northflank.com/pricing),
[templates](https://northflank.com/docs/v1/application/infrastructure-as-code/write-a-template),
[secret scope](https://northflank.com/docs/v1/application/infrastructure-as-code/make-a-template-dynamic),
[entrypoints](https://northflank.com/docs/v1/application/run/override-command-entrypoint).
