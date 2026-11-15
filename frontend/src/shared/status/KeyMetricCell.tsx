import type { KeyMetric } from "@/shared/api/types";
import { formatNumber, formatValue, metricLabel } from "@/shared/format/number";

import { RangeMeter } from "./RangeMeter";
import { STATE_TEXT } from "./stateText";
import { StatusIndicator } from "./StatusIndicator";
import { Timestamp } from "./Timestamp";

function Availability({ metric }: { metric: KeyMetric }) {
  // A stale evaluation is no evidence of the current probe result, up or down (D-02).
  if (metric.value === null || metric.state === "unknown") {
    return (
      <span className="inline-flex items-center gap-1.5 font-medium text-status-unknown">
        <StatusIndicator state="unknown" size="sm" />
        no current probe result
      </span>
    );
  }
  if (metric.aggregation === "ratio") {
    const share = `${formatNumber(metric.value * 100)} % of probes answered (${String(metric.window_seconds)} s)`;
    if (metric.state === "healthy") return <span>{share}</span>;
    return (
      <span className={`inline-flex items-center gap-1.5 font-medium ${STATE_TEXT[metric.state]}`}>
        <StatusIndicator state={metric.state} size="sm" />
        {share}
      </span>
    );
  }
  if (metric.value >= 1) return <span>Answering probes</span>;
  if (metric.state === "healthy") {
    return <span>Probe failed, not yet confirmed ({metric.rule.key} debounce)</span>;
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium whitespace-nowrap ${STATE_TEXT[metric.state]}`}
    >
      <StatusIndicator state={metric.state} size="sm" />
      DOWN
      {metric.since !== null && (
        <>
          {" "}
          since <Timestamp iso={metric.since} />
        </>
      )}
      <span className="data font-normal text-text-muted max-lg:hidden">({metric.rule.key})</span>
    </span>
  );
}

/** The key metric chosen by the API, drawn the way its kind calls for (§6.1). */
export function KeyMetricCell({ metric }: { metric: KeyMetric | null }) {
  if (metric === null) {
    return <span className="text-text-muted">Not evaluated yet</span>;
  }
  return (
    <span className="flex items-center gap-3">
      <span className="w-24 flex-none text-small text-text-muted max-lg:hidden">
        {metricLabel(metric.name)}
      </span>
      {metric.kind === "meter" && <RangeMeter metric={metric} />}
      {metric.kind === "availability" && <Availability metric={metric} />}
      {metric.kind === "value" && (
        <span className="data">
          {metric.value === null ? "no data" : formatValue(metric.value, metric.unit)}
        </span>
      )}
    </span>
  );
}
