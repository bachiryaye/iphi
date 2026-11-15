import { STATE_LABEL, STATE_TEXT } from "./stateText";
import { type IndicatorState, StatusIndicator } from "./StatusIndicator";

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
      className={`inline-flex items-center whitespace-nowrap ${STATE_TEXT[state]} ${state === "healthy" ? "" : "font-semibold"} ${
        size === "lg" ? "gap-2 text-heading" : "gap-1.5"
      }`}
    >
      <StatusIndicator state={state} size={size} />
      {label ?? STATE_LABEL[state]}
    </span>
  );
}
