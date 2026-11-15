import { formatLocalTime, formatUtcTime } from "@/shared/format/time";
import { useNow } from "@/shared/hooks/useNow";

/** Wall-clock time of the viewer's machine; platform time is shown separately from US-02. */
export function Clock() {
  const now = useNow();

  return (
    <div className="text-right font-mono tabular-nums">
      <time dateTime={now.toISOString()} className="block text-data font-medium">
        {formatUtcTime(now)} UTC
      </time>
      <span className="block text-small text-text-muted">{formatLocalTime(now)} local</span>
    </div>
  );
}
