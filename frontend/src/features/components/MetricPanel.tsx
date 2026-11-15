import { useMemo } from "react";

import { REFRESH_MS, type SeriesRequest, useMetricSeries } from "@/shared/api/queries";
import type { ComponentDetail, RuleStatus } from "@/shared/api/types";
import { MetricChart } from "@/shared/charts/MetricChart";
import { metricLabel } from "@/shared/format/number";
import { usePlatformNow } from "@/shared/hooks/usePlatformNow";
import { useSearchFilter } from "@/shared/hooks/useSearchFilter";
import { SimTag } from "@/shared/status/SimTag";
import { Card } from "@/shared/ui/Card";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";
import { Segmented } from "@/shared/ui/Segmented";

import { thresholdsFor } from "./thresholds";

const WINDOWS = [
  { value: "15m", label: "15m", seconds: 15 * 60 },
  { value: "1h", label: "1h", seconds: 3600 },
  { value: "6h", label: "6h", seconds: 6 * 3600 },
  { value: "24h", label: "24h", seconds: 24 * 3600 },
] as const;
type WindowKey = (typeof WINDOWS)[number]["value"];
const WINDOW_KEYS: readonly WindowKey[] = WINDOWS.map((w) => w.value);

interface MetricPanelProps {
  detail: ComponentDetail;
  rules: readonly RuleStatus[];
}

export function MetricPanel({ detail, rules }: MetricPanelProps) {
  const metrics = [
    ...new Set(rules.flatMap((r) => (r.rule.metric_name === null ? [] : [r.rule.metric_name]))),
  ];
  const [chosen, setChosen] = useSearchFilter("metric", metrics);
  const [windowParam, setWindowKey] = useSearchFilter("window", WINDOW_KEYS);
  const windowKey: WindowKey = windowParam === "" ? "15m" : windowParam;
  const metric = (chosen === "" ? null : chosen) ?? detail.key_metric?.name ?? metrics[0] ?? null;
  const platformNow = usePlatformNow(REFRESH_MS);
  const nowMs = platformNow?.getTime() ?? null;
  const windowSeconds = WINDOWS.find((w) => w.value === windowKey)?.seconds ?? 900;

  const request: SeriesRequest | null =
    metric === null || nowMs === null
      ? null
      : {
          componentId: detail.id,
          metricName: metric,
          from: new Date(nowMs - windowSeconds * 1000).toISOString(),
          to: new Date(nowMs).toISOString(),
        };
  const series = useMetricSeries(request);
  const thresholds = useMemo(
    () => (metric === null ? [] : thresholdsFor(metric, rules)),
    [metric, rules],
  );

  return (
    <Card
      title="Metric history"
      titleId="metric-title"
      busy={series.isPending && request !== null}
      meta={
        <>
          {metrics.length > 1 && metric !== null && (
            <Segmented
              label="Metric"
              options={metrics.map((m) => ({ value: m, label: metricLabel(m) }))}
              value={metric}
              onChange={setChosen}
            />
          )}
          <Segmented
            label="Time window"
            options={WINDOWS}
            value={windowKey}
            onChange={setWindowKey}
          />
          <span>UTC</span>
          <SimTag />
          <RefreshMeta updatedAt={series.dataUpdatedAt} failed={series.isError} />
        </>
      }
    >
      {metric === null && (
        <EmptyState title="No measured metric.">
          No rule on {detail.key} measures a metric yet; rules appear after the first evaluation.
        </EmptyState>
      )}
      {metric !== null && series.isPending && <SkeletonRows rows={5} />}
      {series.isError && series.data === undefined && (
        <LoadError what="the metric history" query={series} />
      )}
      {series.data !== undefined && (
        <div className={staleClass(series.isError)}>
          <MetricChart series={series.data} thresholds={thresholds} />
        </div>
      )}
    </Card>
  );
}
