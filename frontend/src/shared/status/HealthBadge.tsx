import type { Translator } from "@/shared/i18n/translate";
import { useT } from "@/shared/i18n/context";
import type { Health } from "@/shared/api/types";
import { formatUtcTime } from "@/shared/format/time";
import { Tooltip } from "@/shared/ui/Tooltip";

import { StatusBadge } from "./StatusBadge";

function unknownReason(health: Health, t: Translator): string {
  if (health.stale_reason !== null) return health.stale_reason;
  if (health.since !== null) {
    return t("No recent evidence since {time} UTC.", {
      time: formatUtcTime(new Date(health.since)),
    });
  }
  return t("No evidence yet.");
}

/** A health state; Unknown always says why (§4: "No recent evidence since …"). */
export function HealthBadge({ health, size = "sm" }: { health: Health; size?: "sm" | "lg" }) {
  const t = useT();
  if (health.state !== "unknown") return <StatusBadge state={health.state} size={size} />;
  return (
    <Tooltip focusable content={unknownReason(health, t)}>
      <StatusBadge state="unknown" size={size} />
      <span className="sr-only">: {unknownReason(health, t)}</span>
    </Tooltip>
  );
}
