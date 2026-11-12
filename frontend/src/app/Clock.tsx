import { useEffect, useState } from "react";

import { formatLocalTime, formatUtcTime } from "@/shared/format/time";

const TICK_MS = 1000;

/** Wall-clock time of the viewer's machine; platform time is shown separately from US-02. */
export function Clock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(new Date());
    }, TICK_MS);
    return () => {
      window.clearInterval(id);
    };
  }, []);

  return (
    <div className="text-right font-mono tabular-nums">
      <time dateTime={now.toISOString()} className="block text-data font-medium">
        {formatUtcTime(now)} UTC
      </time>
      <span className="block text-small text-text-muted">{formatLocalTime(now)} local</span>
    </div>
  );
}
