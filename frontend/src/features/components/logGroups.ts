import type { LogEntry } from "@/shared/api/types";

export interface LogGroup {
  latest: LogEntry;
  count: number;
}

/** Groups by fingerprint, newest first: a burst reads as one line with a count (§6.3). */
export function groupLogs(logs: readonly LogEntry[]): LogGroup[] {
  const groups = new Map<string, LogGroup>();
  for (const log of logs) {
    const group = groups.get(log.fingerprint);
    if (group === undefined) groups.set(log.fingerprint, { latest: log, count: 1 });
    else group.count += 1;
  }
  return [...groups.values()];
}
