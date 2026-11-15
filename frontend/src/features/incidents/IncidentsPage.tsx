import { Link, useSearchParams } from "react-router";

import { type IncidentFilters, useIncidents } from "@/shared/api/queries";
import type { FailureClass, IncidentSeverity, IncidentStatus } from "@/shared/api/types";
import { useSearchFilter } from "@/shared/hooks/useSearchFilter";
import { IncidentStatusLabel } from "@/shared/status/IncidentStatus";
import { SimTag } from "@/shared/status/SimTag";
import { StatusBadge } from "@/shared/status/StatusBadge";
import { Timestamp } from "@/shared/status/Timestamp";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";
import { FilterSelect } from "@/shared/ui/FilterSelect";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";
import { humanize } from "@/shared/format/labels";

const STATUSES: readonly IncidentStatus[] = ["open", "acknowledged", "resolved"];
const SEVERITIES: readonly IncidentSeverity[] = ["critical", "warning"];
const CLASSES: readonly FailureClass[] = [
  "availability", "latency", "freshness", "errors", "resources", "backlog", "connectivity",
  "telemetry_loss",
]; // prettier-ignore
const PAGE_SIZE = 25;

export function IncidentsPage() {
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useSearchFilter("status", STATUSES);
  const [severity, setSeverity] = useSearchFilter("severity", SEVERITIES);
  const [failureClass, setFailureClass] = useSearchFilter("class", CLASSES);
  const cursor = params.get("cursor");
  const filters: IncidentFilters = { limit: PAGE_SIZE };
  if (status !== "") filters.status = [status];
  if (severity !== "") filters.severity = severity;
  if (failureClass !== "") filters.failure_class = failureClass;
  if (cursor !== null) filters.cursor = cursor;
  const incidents = useIncidents(filters);
  const page = incidents.data;
  const filtered = status !== "" || severity !== "" || failureClass !== "";

  const goTo = (next: string | null) => {
    setParams((current) => {
      const updated = new URLSearchParams(current);
      if (next === null) updated.delete("cursor");
      else updated.set("cursor", next);
      return updated;
    });
  };

  return (
    <>
      <h1 className="text-display font-semibold">Incidents</h1>
      <div className="flex flex-wrap items-center gap-4">
        <FilterSelect label="Status" value={status} options={STATUSES} onChange={setStatus} />
        <FilterSelect
          label="Severity"
          value={severity}
          options={SEVERITIES}
          onChange={setSeverity}
        />
        <FilterSelect
          label="Failure class"
          value={failureClass}
          options={CLASSES}
          onChange={setFailureClass}
        />
      </div>
      <Card
        title="Incidents"
        titleId="incidents-title"
        busy={incidents.isPending}
        meta={
          <>
            <span>most recently opened first</span>
            <SimTag />
            <RefreshMeta updatedAt={incidents.dataUpdatedAt} failed={incidents.isError} />
          </>
        }
      >
        {incidents.isPending && <SkeletonRows rows={6} />}
        {incidents.isError && page === undefined && (
          <LoadError
            what="incidents"
            query={incidents}
            stillWorking="Detection continues on the server; only this list is not updating."
          />
        )}
        {page !== undefined && page.items.length === 0 && (
          <EmptyState
            title={filtered ? "No incident matches these filters." : "No incident recorded."}
            action={
              filtered ? undefined : (
                <Link to="/scenarios" className="text-link">
                  Open scenarios
                </Link>
              )
            }
          >
            {filtered
              ? "Clear a filter to widen the list."
              : "Incidents open when a rule stays in Warning or Critical past its debounce. Start a fault scenario to produce one."}
          </EmptyState>
        )}
        {page !== undefined && page.items.length > 0 && (
          <div className={`overflow-x-auto ${staleClass(incidents.isError)}`}>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Severity</th>
                  <th scope="col">Incident</th>
                  <th scope="col">Component</th>
                  <th scope="col">Class</th>
                  <th scope="col">Status</th>
                  <th scope="col">Opened</th>
                  <th scope="col">Last seen</th>
                  <th scope="col" className="num">
                    Occurrences
                  </th>
                  <th scope="col" className="num">
                    Evidence
                  </th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((incident) => (
                  <tr
                    key={incident.id}
                    className={
                      incident.severity === "critical" && incident.status !== "resolved"
                        ? "row-critical"
                        : undefined
                    }
                  >
                    <td>
                      <StatusBadge state={incident.severity} />
                    </td>
                    <th scope="row" className="py-2">
                      <Link to={`/incidents/${incident.id}`} className="text-text hover:underline">
                        <span className="data mr-2 text-text-muted">{incident.reference}</span>
                        <span className="font-medium">{incident.title}</span>
                      </Link>
                    </th>
                    <td>
                      <Link to={`/components/${incident.component.id}`} className="text-link">
                        {incident.component.key}
                      </Link>
                    </td>
                    <td className="text-text-muted">{humanize(incident.failure_class)}</td>
                    <td>
                      <IncidentStatusLabel
                        status={incident.status}
                        acknowledgedBy={incident.acknowledged_by}
                      />
                    </td>
                    <td className="whitespace-nowrap">
                      <Timestamp iso={incident.opened_at} />
                    </td>
                    <td className="whitespace-nowrap text-text-muted">
                      <Timestamp iso={incident.last_seen_at} format="age" />
                    </td>
                    <td className="num data">{incident.occurrence_count}</td>
                    <td className="num data">{incident.evidence_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {page !== undefined && (cursor !== null || page.next_cursor !== null) && (
          <div className="flex items-center gap-2 border-t border-border px-4 py-2.5">
            <Button
              disabled={cursor === null}
              onClick={() => {
                goTo(null);
              }}
            >
              First page
            </Button>
            <Button
              disabled={page.next_cursor === null}
              onClick={() => {
                goTo(page.next_cursor);
              }}
            >
              Next page
            </Button>
          </div>
        )}
      </Card>
    </>
  );
}
