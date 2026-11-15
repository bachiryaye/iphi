import type { IndicatorState } from "./StatusIndicator";

export const STATE_LABEL: Record<IndicatorState, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
  unknown: "Unknown",
};

/** Text colour of a state: neutral when Healthy, the state token otherwise (§4). */
export const STATE_TEXT: Record<IndicatorState, string> = {
  healthy: "text-text",
  warning: "text-status-warning",
  critical: "text-status-critical",
  unknown: "text-status-unknown",
};
