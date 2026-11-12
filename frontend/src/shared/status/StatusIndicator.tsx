export type IndicatorState = "healthy" | "warning" | "critical" | "unknown";

const SIZE = { sm: 14, md: 16, lg: 20 } as const;

interface StatusIndicatorProps {
  state: IndicatorState;
  size?: keyof typeof SIZE;
}

/**
 * HPHMI redundant coding (design system §4, ADR 0009): square for critical, triangle for
 * warning, dashed circle for unknown, neutral hollow circle for healthy. Always paired with text.
 */
export function StatusIndicator({ state, size = "md" }: StatusIndicatorProps) {
  const px = SIZE[size];
  return (
    <svg
      viewBox="0 0 16 16"
      width={px}
      height={px}
      aria-hidden="true"
      focusable="false"
      className="flex-none"
    >
      {state === "critical" && (
        <>
          <rect x="1.5" y="1.5" width="13" height="13" rx="1" className="fill-status-critical" />
          <rect x="7.25" y="3.75" width="1.5" height="6" className="fill-on-critical" />
          <rect x="7.25" y="10.75" width="1.5" height="1.5" className="fill-on-critical" />
        </>
      )}
      {state === "warning" && (
        <>
          <path
            d="M8 1.6 15.2 14.4H.8z"
            strokeWidth="1"
            strokeLinejoin="round"
            className="fill-status-warning-fill stroke-status-warning"
          />
          <rect x="7.3" y="5.6" width="1.4" height="4.8" className="fill-on-warning" />
          <rect x="7.3" y="11.4" width="1.4" height="1.4" className="fill-on-warning" />
        </>
      )}
      {state === "unknown" && (
        <>
          <circle
            cx="8"
            cy="8"
            r="6.5"
            strokeWidth="1.5"
            strokeDasharray="2.6 1.7"
            className="fill-transparent stroke-status-unknown"
          />
          <path
            d="M6.2 6.4a1.8 1.8 0 1 1 2.6 1.6c-.5.3-.8.6-.8 1.2v.4"
            strokeWidth="1.4"
            strokeLinecap="round"
            className="fill-transparent stroke-status-unknown"
          />
          <rect x="7.3" y="10.6" width="1.4" height="1.4" className="fill-status-unknown" />
        </>
      )}
      {state === "healthy" && (
        <circle
          cx="8"
          cy="8"
          r="5"
          strokeWidth="1.5"
          className="fill-transparent stroke-border-strong"
        />
      )}
    </svg>
  );
}
