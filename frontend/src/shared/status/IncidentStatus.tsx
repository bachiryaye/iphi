import { CheckmarkOutline } from "@carbon/icons-react";

import type { IncidentStatus as Status } from "@/shared/api/types";

const LABEL: Record<Status, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
};

interface IncidentStatusProps {
  status: Status;
  acknowledgedBy?: string | null;
}

/** Open: filled dot; Acknowledged: hollow dot and who; Resolved: check, muted text (§4). */
export function IncidentStatusLabel({ status, acknowledgedBy }: IncidentStatusProps) {
  if (status === "resolved") {
    return (
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-text-muted">
        <CheckmarkOutline size={16} aria-hidden="true" />
        {LABEL.resolved}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <span
        aria-hidden="true"
        className={`size-2 rounded-full border-2 border-text ${status === "open" ? "bg-text" : ""}`}
      />
      {LABEL[status]}
      {status === "acknowledged" && acknowledgedBy != null && (
        <span className="text-small text-text-muted">by {acknowledgedBy}</span>
      )}
    </span>
  );
}
