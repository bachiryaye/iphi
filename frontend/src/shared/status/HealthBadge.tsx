import type { Health } from "@/shared/api/types";
import { formatUtcTime } from "@/shared/format/time";
import { Tooltip } from "@/shared/ui/Tooltip";

import { StatusBadge } from "./StatusBadge";

function unknownReason(health: Health): string {
  if (health.stale_reason !== null) return health.stale_reason;
  if (health.since !== null) {
    return `No recent evidence since ${formatUtcTime(new Date(health.since))} UTC.`;
  }
  return "No evidence yet.";
}

/** A health state; Unknown always says why (§4: "No recent evidence since …"). */
export function HealthBadge({ health, size = "sm" }: { health: Health; size?: "sm" | "lg" }) {
  if (health.state !== "unknown") return <StatusBadge state={health.state} size={size} />;
  return (
    <Tooltip focusable content={unknownReason(health)}>
      <StatusBadge state="unknown" size={size} />
      <span className="sr-only">: {unknownReason(health)}</span>
    </Tooltip>
  );
}
