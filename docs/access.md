# Sessions, roles and audit

IPHI is a local simulated demonstrator. Run `make init-env` before a direct
`docker compose up --build`, or use `make up` / `make demo`, which initialize the
credentials themselves. Missing passwords are generated in the ignored `.env`
with file mode 600; existing values, including provider configuration, are preserved.
Use an editor to inspect or replace these local values; do not copy them into issues
or screenshots. No password is built into the image or repository.

Open the interface and sign in as `viewer`, `engineer` or `admin`, using the
corresponding `IPHI_DEMO_*_PASSWORD`. All observations remain explicitly simulated.

| Role | Permitted actions |
|---|---|
| viewer | Read monitoring, evidence, history, diagnostics and PDF/CSV reports |
| engineer | Viewer access, start/stop scenarios, change the clock, acknowledge/resolve/comment/diagnose incidents |
| admin | Engineer access, reset the simulation and read/filter/page the audit journal |

Operational controls remain visible but disabled with a role explanation when
permission is missing. Audit navigation appears for admin only. The server enforces
the same permissions independently; manually sending a forbidden request returns
403 and records a denied audit event with the actor and correlation ID.

Sessions use an HttpOnly, SameSite=Strict cookie and expire after eight wall-clock
hours, independently of the simulation clock. Sign out revokes the server session.
Mutations require a session-bound `X-CSRF-Token`, JSON content type and the same-origin
browser boundary. The browser keeps the CSRF proof in memory; it never stores the
session secret in localStorage or sessionStorage. An expired session returns to sign-in.
SSE connections recheck session validity at most fifteen seconds apart.

Login attempts are persisted and limited to six per username and twenty globally
per minute; concurrent password verification is bounded. A busy or limited login
returns 429. Passwords use Argon2id. Change an explicit password in `.env`, then run
the migration/bootstrap job again; that account's existing sessions are revoked.
Removing a password from configuration does not delete an existing account.
There is no account-management API in this story.

`IPHI_DEPLOYMENT_MODE=local` requires loopback binding and permits HTTP cookies.
`production` adds Secure cookies and requires an HTTPS ingress supplied by the
operator; no public deployment is included or claimed. Health, readiness, OpenAPI
and login are public. All operational API reads require a valid session.

## Authenticated API examples

The command-line demo/performance tools sign in automatically using the admin
password supplied to the API container. For the README's curl examples, run this
setup in a shell with Python 3 and curl. It prompts without echoing the password and
stores the session only in a temporary directory accessible to its owner.

```sh
IPHI_SESSION_DIR=$(python3 - <<'PY'
import getpass
import http.cookiejar
import json
import os
import tempfile
import urllib.request
from pathlib import Path

directory = Path(tempfile.mkdtemp(prefix="iphi-session-"))
cookies = http.cookiejar.MozillaCookieJar(str(directory / "cookies"))
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cookies)
)
with open("/dev/tty", "r+") as terminal:
    terminal.write("Username: ")
    terminal.flush()
    username = terminal.readline().strip()
credentials = {"username": username, "password": getpass.getpass("Password: ")}
request = urllib.request.Request(
    "http://127.0.0.1:8080/api/v1/auth/login",
    data=json.dumps(credentials).encode(), headers={"content-type": "application/json"},
)
with opener.open(request, timeout=30) as response:
    session = json.load(response)
cookies.save(ignore_discard=True)
os.chmod(directory / "cookies", 0o600)
with os.fdopen(os.open(directory / "headers", os.O_WRONLY | os.O_CREAT, 0o600), "w") as stream:
    stream.write("X-CSRF-Token: " + session["csrf_token"] + "\n")
print(directory)
PY
)
iphi_request() {
  curl -fsS --cookie "$IPHI_SESSION_DIR/cookies" --header "@$IPHI_SESSION_DIR/headers" "$@"
}
```

For the demo stack, replace port 8080 with 8081 in the login URL. Use `iphi_request`
only with that local IPHI instance. The cookie is host-scoped; sessions on two local
stacks sharing a hostname can overwrite each other in the browser. Use separate
browser profiles or sign in again when switching stacks.

```sh
iphi_request http://127.0.0.1:8080/api/v1/platforms
iphi_request http://127.0.0.1:8080/api/v1/simulations/scenarios \
  -H 'content-type: application/json' -d '{"scenario_key":"collector_down"}'
iphi_request http://127.0.0.1:8080/api/v1/audit-events   # admin
iphi_request http://127.0.0.1:8080/api/v1/auth/logout \
  -H 'content-type: application/json' -d '{}'
```

Delete the temporary directory after sign-out. Never share cookie or header files.
Playwright similarly creates disposable, ignored session files under
`frontend/.playwright/`; they are not source files or screenshots.

See [ADR 0025](adr/0025-identity-sessions-us11.md) and the
[identity threat model](security/identity-threat-model.md).
