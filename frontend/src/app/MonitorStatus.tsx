import { Activity } from "@carbon/icons-react";
import type { ReactNode } from "react";

import { type CheckName, type Readiness, useReadiness } from "@/shared/api/readiness";
import { formatSeconds, formatUtcTime } from "@/shared/format/time";
import { StatusBadge } from "@/shared/status/StatusBadge";

const FAILURE_LABEL: Record<CheckName, string> = {
  database: "Database unreachable",
  migrations: "Schema out of date",
  worker: "Monitor stalled",
  ai_provider: "AI provider failing",
};

function Item({ children }: { children: ReactNode }) {
  return <span className="flex items-center gap-1.5 whitespace-nowrap">{children}</span>;
}

function MonitorState({ readiness }: { readiness: Readiness }) {
  const failed = readiness.checks.find((check) => check.status === "failed");
  if (failed) return <StatusBadge state="critical" label={FAILURE_LABEL[failed.name]} />;
  return (
    <Item>
      <Activity size={16} aria-hidden="true" />
      Monitor running
    </Item>
  );
}

function CycleDetails({ readiness }: { readiness: Readiness }) {
  const worker = readiness.checks.find((check) => check.name === "worker");
  const ai = readiness.checks.find((check) => check.name === "ai_provider");
  const lastCycle = worker?.observed_at ? formatUtcTime(new Date(worker.observed_at)) : null;
  return (
    <>
      <Item>
        Cycle {formatSeconds(readiness.cycle_interval_s)}
        {lastCycle !== null && (
          <>
            , last <span className="data">{lastCycle}</span>
          </>
        )}
      </Item>
      {ai?.status === "disabled" && <Item>AI diagnosis off</Item>}
    </>
  );
}

/**
 * The monitor reports on itself in the top bar so it can never fail silently (§5). A failed
 * refresh outranks cached readiness: last known "running" is not evidence of running now.
 */
export function MonitorStatus() {
  const { data, isError, dataUpdatedAt } = useReadiness();

  let state: ReactNode;
  if (isError) state = <StatusBadge state="unknown" label="API unreachable" />;
  else if (data !== undefined) state = <MonitorState readiness={data} />;
  else state = <Item>Checking monitor…</Item>;

  return (
    <div
      role="group"
      aria-label="Monitor status"
      className="flex items-center gap-4 text-small text-text-muted max-lg:[&>*:not(:first-child)]:hidden"
    >
      {/* Only state changes are announced; the cycle time below changes on every poll. */}
      <span aria-live="polite" className="flex">
        {state}
      </span>
      {isError && data !== undefined && (
        <Item>
          Last answer <span className="data">{formatUtcTime(new Date(dataUpdatedAt))} UTC</span>
        </Item>
      )}
      {!isError && data !== undefined && <CycleDetails readiness={data} />}
    </div>
  );
}
