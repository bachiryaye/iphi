import { formatLocalTime, formatUtcTime } from "@/shared/format/time";
import { usePlatformNow } from "@/shared/hooks/usePlatformNow";

/** The same simulated platform clock used by observations and incident timestamps. */
export function Clock() {
  const now = usePlatformNow(1000);

  return (
    <div className="text-right font-mono tabular-nums">
      {now === null ? (
        <span>Platform time loading…</span>
      ) : (
        <>
          <time dateTime={now.toISOString()} className="block text-data font-medium">
            {formatUtcTime(now)} UTC
          </time>
          <span className="block text-small text-text-muted">
            Platform · {formatLocalTime(now)} local
          </span>
        </>
      )}
    </div>
  );
}
