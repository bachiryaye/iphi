# ADR 0025 — Server sessions and authorization (US-11)

- Status: accepted, implementation details within approved US-11 / ADR 0007
- Date: 2026-11-18

## Context

ADR 0007 requires server sessions, Argon2id, CSRF, viewer/engineer/admin and
audited refusals. The local simulated demonstrator remains the deployment scope.
Authentication replaces the earlier development mutation switch without changing
health rules or introducing an identity service outside the modular monolith.

## Decision

Persist users and sessions in migration 0008. Store Argon2id password hashes and
SHA-256 hashes of independent 256-bit random session secrets. Sessions expire after
eight wall-clock hours; every request rechecks the current role and active flag.
Keep at most eight current sessions per user and purge expired/revoked rows in
bounded batches at login. Logout and an explicit environment password change at
bootstrap revoke affected sessions. Simulation reset preserves identity and audit.

The cookie is HttpOnly, SameSite=Strict, path `/`, no Domain, and Secure in
`IPHI_DEPLOYMENT_MODE=production`. Local HTTP mode requires loopback binding.
Login and `/auth/me` return an independent HMAC CSRF proof derived from the session
secret; JavaScript keeps it in memory. Mutations require its header as well as
the existing same-origin JSON boundary. Session secrets never enter response JSON,
URLs, logs or browser storage. Operational reads require a session; health/readiness
and login remain public. No authentication bypass is retained.

The server enforces engineer mutations and admin reset/audit access. Denials retain
actor identity and correlation ID. Login attempts are audited, limited to six per
username and twenty globally per minute, and serialized before Argon2 verification
with a PostgreSQL advisory lock. Unknown usernames use a dummy Argon2 hash and the
same public error. No password, cookie or CSRF proof is audited. SSE revalidates
sessions at most fifteen seconds apart and closes on revocation/expiry.

Demo passwords come from environment only. `make init-env` generates missing local
values atomically in an ignored mode-600 `.env`, preserving existing values and
the provider credential. Bootstrap initializes users; changed explicit passwords
rotate hashes and revoke sessions. There is no user-management API in this story.

For UI permissions, the design system's explicit visible-disabled controls and
role explanations apply to operational actions. Admin navigation is omitted for
other roles; direct access remains denied by the server. This resolves the backlog's
broader “hidden actions” wording without reducing server enforcement.

## Alternatives and consequences

JWT/browser storage and an external identity service remain excluded by ADR 0007.
Eight-hour sessions require periodic sign-in. The persistent global login ceiling
is conservative for a small local demo and can cause temporary shared throttling;
it is not a public multi-tenant identity platform. Argon2 defaults use its maintained
recommended profile. Test credentials are synthetic and confined to disposable DBs.
CLI, CI and browser demonstrations must authenticate through the actual endpoint.

## References

- [argon2-cffi password hashing](https://argon2-cffi.readthedocs.io/en/stable/howto.html)
- [FastAPI cookies](https://fastapi.tiangolo.com/advanced/response-cookies/)
