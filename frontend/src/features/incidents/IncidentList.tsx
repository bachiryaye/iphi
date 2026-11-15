import { Link } from "react-router";

import type { Incident } from "@/shared/api/types";
import { IncidentStatusLabel } from "@/shared/status/IncidentStatus";
import { StatusBadge } from "@/shared/status/StatusBadge";
import { Timestamp } from "@/shared/status/Timestamp";
import { humanize } from "@/shared/format/labels";

const plural = (n: number, word: string) => `${String(n)} ${word}${n === 1 ? "" : "s"}`;

interface IncidentListProps {
  incidents: readonly Incident[];
  /** Stacked rows for a narrow side column. */
  compact?: boolean;
}

function CompactRow({ incident }: { incident: Incident }) {
  return (
    <Link
      to={`/incidents/${incident.id}`}
      className="flex flex-col gap-0.5 px-4 py-2.5 text-text hover:bg-surface-sunken/55"
    >
      <span className="flex items-center gap-2">
        <StatusBadge state={incident.severity} />
        <span className="data text-text-muted">{incident.reference}</span>
        <span className="ml-auto text-data">
          <IncidentStatusLabel status={incident.status} />
        </span>
      </span>
      <span className="truncate font-medium">{incident.title}</span>
      <span className="text-small text-text-muted">
        {humanize(incident.failure_class)}, opened{" "}
        <Timestamp iso={incident.opened_at} format="age" />
      </span>
    </Link>
  );
}

/** Incident rows (Overview, Component): severity, reference, title, status, age. */
export function IncidentList({ incidents, compact = false }: IncidentListProps) {
  return (
    <ul>
      {incidents.map((incident) => (
        <li key={incident.id} className="border-b border-border last:border-b-0">
          {compact ? (
            <CompactRow incident={incident} />
          ) : (
            <Link
              to={`/incidents/${incident.id}`}
              className="grid grid-cols-[84px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-text hover:bg-surface-sunken/55"
            >
              <StatusBadge state={incident.severity} />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="flex items-baseline gap-2 font-medium">
                  <span className="data font-normal text-text-muted">{incident.reference}</span>
                  <span className="truncate">{incident.title}</span>
                </span>
                <span className="flex flex-wrap gap-x-4 text-small text-text-muted">
                  <span>{humanize(incident.failure_class)}</span>
                  <span>{plural(incident.occurrence_count, "occurrence")}</span>
                  <span>{plural(incident.evidence_count, "evidence item")}</span>
                </span>
              </span>
              <span className="flex flex-col items-end gap-0.5 text-data">
                <IncidentStatusLabel
                  status={incident.status}
                  acknowledgedBy={incident.acknowledged_by}
                />
                <Timestamp iso={incident.opened_at} format="age" className="text-text-muted" />
              </span>
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}
