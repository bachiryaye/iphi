import { useT } from "@/shared/i18n/context";
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
  const t = useT();
  const failed = readiness.checks.find(
    (check) => check.status === "failed" && check.name !== "ai_provider",
  );
  if (failed) return <StatusBadge state="critical" label={FAILURE_LABEL[failed.name]} />;
  return (
    <Item>
      <Activity size={16} aria-hidden="true" /> {t("Monitor running")}
    </Item>
  );
}

function CycleDetails({ readiness }: { readiness: Readiness }) {
  const t = useT();
  const worker = readiness.checks.find((check) => check.name === "worker");
  const ai = readiness.checks.find((check) => check.name === "ai_provider");
  const lastCycle = worker?.observed_at ? formatUtcTime(new Date(worker.observed_at)) : null;
  return (
    <>
      <Item>
        {t("Cycle")} {formatSeconds(readiness.cycle_interval_s, t)}
        {lastCycle !== null && (
          <>
            {t(", last")} <span className="data">{lastCycle}</span>
          </>
        )}
      </Item>
      {ai?.status === "disabled" && <Item>{t("AI diagnosis off")}</Item>}
      {ai?.status === "failed" && <Item>{t("AI unavailable · deterministic available")}</Item>}
      {ai?.status === "unknown" && <Item>{t("AI provider unverified")}</Item>}
      {ai?.status === "ok" && <Item>{t("AI provider: last attempt succeeded")}</Item>}
    </>
  );
}

/**
 * The monitor reports on itself in the top bar so it can never fail silently (§5). A failed
 * refresh outranks cached readiness: last known "running" is not evidence of running now.
 */
export function MonitorStatus() {
  const t = useT();
  const { data, isError, dataUpdatedAt } = useReadiness();

  let state: ReactNode;
  if (isError) state = <StatusBadge state="unknown" label={t("API unreachable")} />;
  else if (data !== undefined) state = <MonitorState readiness={data} />;
  else state = <Item>{t("Checking monitor…")}</Item>;

  return (
    <div
      role="group"
      aria-label={t("Monitor status")}
      className="flex items-center gap-4 text-small text-text-muted max-lg:[&>*:not(:first-child)]:hidden"
    >
      {/* Only state changes are announced; the cycle time below changes on every poll. */}
      <span aria-live="polite" className="flex">
        {state}
      </span>
      {isError && data !== undefined && (
        <Item>
          {t("Last answer")}{" "}
          <span className="data">{formatUtcTime(new Date(dataUpdatedAt))} UTC</span>
        </Item>
      )}
      {!isError && data !== undefined && <CycleDetails readiness={data} />}
    </div>
  );
}
