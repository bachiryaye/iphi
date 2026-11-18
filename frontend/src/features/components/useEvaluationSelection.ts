import { useSearchParams } from "react-router";

import type { HistorySegment } from "@/shared/api/types";

export interface EvaluationSelection {
  lane: string;
  from: string;
  to: string;
}

function selectionOf(raw: string | null, lanes: readonly string[]): EvaluationSelection | null {
  if (raw === null || raw.length > 256) return null;
  const parts = raw.split("|");
  const [lane, from, to] = parts;
  if (
    parts.length !== 3 ||
    lane === undefined ||
    from === undefined ||
    to === undefined ||
    !lanes.includes(lane)
  )
    return null;
  const zoned = /(?:Z|[+-]\d{2}:\d{2})$/;
  if (!zoned.test(from) || !zoned.test(to)) return null;
  const start = Date.parse(from),
    end = Date.parse(to);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) return null;
  return { lane, from: new Date(start).toISOString(), to: new Date(end).toISOString() };
}

/** Keep the inspected interval shareable while the outer live window keeps moving. */
export function useEvaluationSelection(lanes: readonly string[]) {
  const [params, setParams] = useSearchParams();
  const selection = selectionOf(params.get("evaluation"), lanes);
  const write = (value: string | null) => {
    setParams(
      (current) => {
        const updated = new URLSearchParams(current);
        if (value === null) updated.delete("evaluation");
        else updated.set("evaluation", value);
        return updated;
      },
      { replace: true },
    );
  };
  return {
    selection,
    choose: (lane: string, segment: Pick<HistorySegment, "from" | "to">) => {
      write([lane, segment.from, segment.to].join("|"));
    },
    clear: () => {
      write(null);
    },
  };
}
