import { type IndicatorState, StatusIndicator } from "./StatusIndicator";

const LABEL: Record<IndicatorState, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
  unknown: "Unknown",
};

const TONE: Record<IndicatorState, string> = {
  healthy: "text-text",
  warning: "font-semibold text-status-warning",
  critical: "font-semibold text-status-critical",
  unknown: "font-semibold text-status-unknown",
};

interface StatusBadgeProps {
  state: IndicatorState;
  /** Replaces the state name when the badge qualifies something other than health. */
  label?: string;
  size?: "sm" | "lg";
}

/** Single rendering of a state: indicator shape, then text, coloured on both (§4). */
export function StatusBadge({ state, label, size = "sm" }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap ${TONE[state]} ${
        size === "lg" ? "gap-2 text-heading" : "gap-1.5"
      }`}
    >
      <StatusIndicator state={state} size={size} />
      {label ?? LABEL[state]}
    </span>
  );
}
