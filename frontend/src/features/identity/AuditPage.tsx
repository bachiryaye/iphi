import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { api, call } from "@/shared/api/client";
import type { components } from "@/shared/api/schema";
import { useSearchFilter } from "@/shared/hooks/useSearchFilter";
import { useSession } from "@/shared/identity/session";
import { Timestamp } from "@/shared/status/Timestamp";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { FilterSelect } from "@/shared/ui/FilterSelect";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";

type Action = components["schemas"]["AuditAction"];
type Outcome = components["schemas"]["AuditOutcome"];
const ACTIONS: readonly Action[] = [
  "auth.login",
  "auth.logout",
  "scenario.start",
  "scenario.stop",
  "simulation.reset",
  "clock.update",
  "incident.ack",
  "incident.resolve",
  "incident.diagnose",
  "incident.comment",
  "audit.read",
  "identity.user.seed",
  "identity.password.rotate",
];
const OUTCOMES: readonly Outcome[] = ["allowed", "denied", "failed"];

export function AuditPage() {
  const session = useSession();
  const [params, setParams] = useSearchParams();
  const [action, setAction] = useSearchFilter("action", ACTIONS);
  const [outcome, setOutcome] = useSearchFilter("outcome", OUTCOMES);
  const [anchor, setAnchor] = useState(() => Date.now());
  const cursor = params.get("cursor");
  const filters = {
    from: new Date(anchor - 86_400_000).toISOString(),
    to: new Date(anchor).toISOString(),
    action: action || null,
    outcome: outcome || null,
    cursor,
    limit: 50,
  };
  const query = useQuery({
    queryKey: ["audit", filters],
    queryFn: () => call(api.GET("/api/v1/audit-events", { params: { query: filters } })),
    enabled: session.data?.user.role === "admin",
  });
  const goTo = (next: string | null) => {
    setParams((current) => {
      const updated = new URLSearchParams(current);
      if (next === null) updated.delete("cursor");
      else updated.set("cursor", next);
      return updated;
    });
  };
  if (session.data?.user.role !== "admin") {
    return (
      <>
        <h1 className="text-display font-semibold">Audit</h1>
        <p>
          The audit journal requires the admin role. Your role is{" "}
          {session.data?.user.role ?? "unavailable"}.
        </p>
      </>
    );
  }
  return (
    <>
      <h1 className="text-display font-semibold">Audit journal</h1>
      <p className="text-text-muted">
        Wall-clock UTC. Sensitive actions and refused attempts in the last 24 hours; simulation
        resets preserve this journal.
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <FilterSelect label="Action" value={action} options={ACTIONS} onChange={setAction} />
        <FilterSelect label="Outcome" value={outcome} options={OUTCOMES} onChange={setOutcome} />
        <Button
          onClick={() => {
            goTo(null);
            setAnchor(Date.now());
          }}
        >
          Refresh latest
        </Button>
      </div>
      <Card
        title="Audit events"
        titleId="audit-title"
        busy={query.isPending}
        meta={<RefreshMeta updatedAt={query.dataUpdatedAt} failed={query.isError} />}
      >
        {query.isPending && <SkeletonRows rows={6} />}
        {query.isError && <LoadError what="the audit journal" query={query} />}
        {query.data?.items.length === 0 && (
          <EmptyState title="No matching audit events.">
            Choose another action or outcome, or refresh the current interval.
          </EmptyState>
        )}
        {query.data !== undefined && query.data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <caption className="sr-only">
                Audit events, newest first. Timestamps use wall-clock UTC.
              </caption>
              <thead className="text-small text-text-muted">
                <tr>
                  {[
                    "Time (UTC)",
                    "Actor",
                    "Action",
                    "Target",
                    "Outcome",
                    "Correlation / details",
                  ].map((title) => (
                    <th
                      key={title}
                      scope="col"
                      className="border-b border-border px-4 py-3 font-medium"
                    >
                      {title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((event) => (
                  <tr key={event.id}>
                    <td className="whitespace-nowrap border-b border-border px-4 py-3">
                      <Timestamp iso={event.occurred_at} />
                    </td>
                    <td className="border-b border-border px-4 py-3">{event.actor_label}</td>
                    <td className="data border-b border-border px-4 py-3">{event.action}</td>
                    <td className="data max-w-48 border-b border-border px-4 py-3 break-words">
                      {event.target_type ?? "—"}
                      <br />
                      {event.target_id}
                    </td>
                    <td className="border-b border-border px-4 py-3">{event.outcome}</td>
                    <td className="max-w-72 border-b border-border px-4 py-3">
                      <details>
                        <summary className="cursor-pointer">Inspect event</summary>
                        <p className="data break-all">
                          {event.correlation_id ?? "No correlation ID"}
                        </p>
                        <pre className="mt-2 text-small whitespace-pre-wrap break-words">
                          {JSON.stringify(event.details, null, 2)}
                        </pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex gap-3 px-4 py-3">
          {cursor !== null && (
            <Button
              onClick={() => {
                goTo(null);
              }}
            >
              First page
            </Button>
          )}
          {query.data?.next_cursor && (
            <Button
              onClick={() => {
                goTo(query.data.next_cursor);
              }}
            >
              Next page
            </Button>
          )}
        </div>
      </Card>
    </>
  );
}
