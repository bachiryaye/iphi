import type { Readiness } from "@/shared/api/readiness";

export const readyBody: Readiness = {
  status: "ready",
  checked_at: "2026-11-12T10:42:07Z",
  cycle_interval_s: 5,
  checks: [
    { name: "database", status: "ok", detail: "PostgreSQL reachable.", observed_at: null },
    { name: "migrations", status: "ok", detail: "At revision 0001.", observed_at: null },
    {
      name: "worker",
      status: "ok",
      detail: "Last cycle took 3 ms.",
      observed_at: "2026-11-12T10:42:05Z",
    },
    {
      name: "ai_provider",
      status: "disabled",
      detail: "LLM provider 'none'; deterministic diagnosis only.",
      observed_at: null,
    },
  ],
};

export const stalledBody: Readiness = {
  ...readyBody,
  status: "not_ready",
  checks: readyBody.checks.map((check) =>
    check.name === "worker"
      ? {
          ...check,
          status: "failed",
          detail: "Worker stalled: last cycle 80 s ago, expected every 5 s.",
          observed_at: "2026-11-12T10:40:47Z",
        }
      : check,
  ),
};
