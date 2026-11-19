import { useT } from "@/shared/i18n/context";
import { formatAge, formatFullTimestamp, formatUtcTime } from "@/shared/format/time";
import { usePlatformClock } from "@/shared/hooks/usePlatformNow";

interface TimestampProps {
  iso: string;
  /**
   * `time`: 10:42:07 UTC; `age`: 4 min ago, against platform time like every stored instant.
   * The other form is always in the title (P6).
   */
  format?: "time" | "age";
  suffix?: boolean;
  className?: string;
}

export function Timestamp({ iso, format = "time", suffix = true, className = "" }: TimestampProps) {
  const t = useT();
  const at = new Date(iso);
  return (
    <time dateTime={iso} title={formatFullTimestamp(at, t)} className={`data ${className}`}>
      {format === "age" ? <Age at={at} /> : `${formatUtcTime(at)}${suffix ? " UTC" : ""}`}
    </time>
  );
}

function Age({ at }: { at: Date }) {
  const t = useT();
  const now = usePlatformClock();
  return <>{formatAge(at, now, t)}</>;
}
