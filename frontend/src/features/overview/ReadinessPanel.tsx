import {
  type CheckName,
  type Readiness,
  type ReadinessCheck,
  READINESS_REFRESH_MS,
  useReadiness,
} from "@/shared/api/readiness";
import { formatUtcTime } from "@/shared/format/time";
import { StatusBadge } from "@/shared/status/StatusBadge";
import { Timestamp } from "@/shared/status/Timestamp";
import { Card } from "@/shared/ui/Card";
import { LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

const CHECK_LABEL: Record<CheckName, string> = {
  database: "Database",
  migrations: "Schema migrations",
  worker: "Worker heartbeat",
  ai_provider: "AI diagnosis provider",
};

const REFRESH_S = READINESS_REFRESH_MS / 1000;

function CheckStatusCell({ status }: { status: ReadinessCheck["status"] }) {
  if (status === "ok") return <StatusBadge state="healthy" label="OK" />;
  if (status === "failed") return <StatusBadge state="critical" label="Failed" />;
  return (
    <span className="inline-flex items-center gap-1.5 text-text-muted">
      <span aria-hidden="true" className="w-3.5" />
      Off
    </span>
  );
}

function Verdict({ readiness }: { readiness: Readiness }) {
  const ready = readiness.status === "ready";
  const failed = readiness.checks.filter((check) => check.status === "failed").length;
  return (
    <div className="flex items-center gap-2 px-4 py-4">
      <StatusBadge
        state={ready ? "healthy" : "critical"}
        label={ready ? "API ready" : "API not ready"}
        size="lg"
      />
      {!ready && (
        <p className="text-text-muted">
          {failed === 1 ? "1 check failed." : `${String(failed)} checks failed.`}
        </p>
      )}
    </div>
  );
}

function ChecksTable({ checks }: { checks: readonly ReadinessCheck[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="text-left text-small text-text-muted">
            <th scope="col" className="border-y border-border py-2 pr-3 pl-4 font-medium">
              Check
            </th>
            <th scope="col" className="border-y border-border px-3 py-2 font-medium">
              Status
            </th>
            <th scope="col" className="border-y border-border px-3 py-2 font-medium">
              Detail
            </th>
            <th scope="col" className="border-y border-border py-2 pr-4 pl-3 font-medium">
              Evidence time
            </th>
          </tr>
        </thead>
        <tbody>
          {checks.map((check) => (
            <tr
              key={check.name}
              className={
                check.status === "failed"
                  ? "[&>*:first-child]:shadow-[inset_3px_0_0_var(--status-critical)]"
                  : undefined
              }
            >
              <th
                scope="row"
                className="h-11 border-b border-border py-0 pr-3 pl-4 text-left font-medium whitespace-nowrap"
              >
                {CHECK_LABEL[check.name]}
              </th>
              <td className="border-b border-border px-3 whitespace-nowrap">
                <CheckStatusCell status={check.status} />
              </td>
              <td className="border-b border-border px-3">{check.detail}</td>
              <td className="border-b border-border pr-4 pl-3 whitespace-nowrap">
                {check.observed_at ? (
                  <Timestamp iso={check.observed_at} />
                ) : (
                  <span className="text-text-muted">
                    <span aria-hidden="true">—</span>
                    <span className="sr-only">No evidence time</span>
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReadinessPanel() {
  const readiness = useReadiness();
  const { data, isPending, isError, dataUpdatedAt } = readiness;
  const stale = isError && data !== undefined;

  const meta =
    data === undefined ? undefined : stale ? (
      <RefreshMeta updatedAt={dataUpdatedAt} failed />
    ) : (
      <span>
        Checked <span className="data">{formatUtcTime(new Date(data.checked_at))} UTC</span>,
        refreshes every {REFRESH_S}&nbsp;s
      </span>
    );

  return (
    <Card title="Monitor readiness" titleId="readiness-title" meta={meta} busy={isPending}>
      {isPending && <SkeletonRows />}
      {isError && data === undefined && <LoadError what="monitor readiness" query={readiness} />}
      {data !== undefined && (
        <div className={staleClass(stale)}>
          <Verdict readiness={data} />
          <ChecksTable checks={data.checks} />
        </div>
      )}
    </Card>
  );
}
