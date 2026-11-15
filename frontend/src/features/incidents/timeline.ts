import type { IncidentEvent } from "@/shared/api/types";

export type Entry =
  { kind: "event"; event: IncidentEvent } | { kind: "occurrences"; events: IncidentEvent[] };

/** Consecutive occurrences collapse into one row: the visible proof of no incident storm. */
export function groupTimeline(events: readonly IncidentEvent[]): Entry[] {
  const entries: Entry[] = [];
  for (const event of events) {
    const last = entries[entries.length - 1];
    if (event.type === "occurrence" && last?.kind === "occurrences") last.events.push(event);
    else if (event.type === "occurrence") entries.push({ kind: "occurrences", events: [event] });
    else entries.push({ kind: "event", event });
  }
  return entries;
}
