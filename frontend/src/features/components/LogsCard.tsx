import { useLogs } from "@/shared/api/queries";
import type { LogEntry } from "@/shared/api/types";
import { SimTag } from "@/shared/status/SimTag";
import { Timestamp } from "@/shared/status/Timestamp";
import { Card } from "@/shared/ui/Card";
import { LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

import { groupLogs } from "./logGroups";

const SEVERITY_TONE: Record<LogEntry["severity"], string> = {
  debug: "text-text-muted",
  info: "text-text-muted",
  warning: "text-status-warning",
  error: "text-status-critical",
  critical: "text-status-critical",
};

export function LogsCard({ componentId }: { componentId: string }) {
  const logs = useLogs(componentId, "warning");
  const groups = logs.data === undefined ? [] : groupLogs(logs.data.items);
  return (
    <Card
      title="Recent logs"
      titleId="logs-title"
      busy={logs.isPending}
      meta={
        <>
          <span>warning and above, last hour, grouped by fingerprint</span>
          <SimTag />
          <RefreshMeta updatedAt={logs.dataUpdatedAt} failed={logs.isError} />
        </>
      }
    >
      {logs.isPending && <SkeletonRows rows={3} />}
      {logs.isError && logs.data === undefined && <LoadError what="logs" query={logs} />}
      {logs.data !== undefined && groups.length === 0 && (
        <p className="px-4 py-3 text-text-muted">
          No warning or error log in the last hour of platform time.
        </p>
      )}
      {groups.length > 0 && (
        <div className={`overflow-x-auto ${staleClass(logs.isError)}`}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Latest (UTC)</th>
                <th scope="col">Severity</th>
                <th scope="col">Message</th>
                <th scope="col" className="num">
                  Count
                </th>
                <th scope="col">Fingerprint</th>
              </tr>
            </thead>
            <tbody>
              {groups.map(({ latest, count }) => (
                <tr key={latest.fingerprint}>
                  <td className="whitespace-nowrap">
                    <Timestamp iso={latest.observed_at} suffix={false} />
                  </td>
                  <td className={`data font-medium uppercase ${SEVERITY_TONE[latest.severity]}`}>
                    {latest.severity === "warning" ? "warn" : latest.severity}
                  </td>
                  <td className="py-2">{latest.message}</td>
                  <td className="num data">{count}</td>
                  <td className="data text-text-muted" translate="no">
                    {latest.fingerprint.slice(0, 8)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {logs.data?.next_cursor != null && (
        <p className="border-t border-border px-4 py-2.5 text-small text-text-muted">
          Grouped from the latest 100 entries; older ones are not shown.
        </p>
      )}
    </Card>
  );
}
