import { useMemo, useState } from "react";

import {
  REFRESH_MS,
  type SeriesRequest,
  useMetricSeries,
  useStateHistory,
  useInvestigationRuns,
  useIncidents,
} from "@/shared/api/queries";
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
import { StateBand } from "./StateBand";

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
  const historyRequest = useMemo(
    () =>
      nowMs === null
        ? null
        : {
            componentId: detail.id,
            from: new Date(nowMs - windowSeconds * 1000).toISOString(),
            to: new Date(nowMs).toISOString(),
          },
    [detail.id, nowMs, windowSeconds],
  );
  const history = useStateHistory(historyRequest);
  const incidents = useIncidents({ component_id: detail.id, limit: 100 });
  const runs = useInvestigationRuns();
  const [cursor, setCursor] = useState<number | null>(null);
  const markers = useMemo(
    () =>
      incidents.data?.items
        .flatMap((i) => [
          { at: i.opened_at, label: `${i.reference} opened` },
          ...(i.resolved_at === null
            ? []
            : [{ at: i.resolved_at, label: `${i.reference} resolved` }]),
        ])
        .filter(
          (m) =>
            historyRequest !== null &&
            Date.parse(m.at) >= Date.parse(historyRequest.from) &&
            Date.parse(m.at) < Date.parse(historyRequest.to),
        )
        .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
        .map((marker, index) => ({ ...marker, showLabel: index === 0 })) ?? [],
    [incidents.data, historyRequest],
  );
  const spans =
    runs.data?.items
      .filter((r) => r.target_component_key === null || r.target_component_key === detail.key)
      .map((r) => ({
        from: r.started_at,
        to: r.stopped_at ?? r.ends_at ?? historyRequest?.to ?? r.started_at,
        label: `SIM ${r.scenario_key} #${String(r.number)}`,
      }))
      .filter(
        (r) =>
          historyRequest !== null &&
          Date.parse(r.from) < Date.parse(historyRequest.to) &&
          Date.parse(r.to) > Date.parse(historyRequest.from),
      ) ?? [];
  const thresholds = useMemo(
    () => (metric === null ? [] : thresholdsFor(metric, rules)),
    [metric, rules],
  );
  const aligned =
    history.data === undefined ||
    series.data === undefined ||
    (Date.parse(history.data.from) === Date.parse(series.data.window_start) &&
      Date.parse(history.data.to) === Date.parse(series.data.window_end));

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
      {historyRequest !== null && history.isPending && <SkeletonRows rows={3} />}
      {history.isError && history.data === undefined && (
        <LoadError what="recorded state history" query={history} />
      )}
      {!aligned && (
        <p className="px-4 py-2 text-small text-text-muted" role="status">
          Aligning the recorded states and metric window…
        </p>
      )}
      {history.data !== undefined && aligned && (
        <div className={staleClass(history.isError)}>
          <StateBand
            history={history.data}
            series={series.data}
            cursor={cursor}
            onCursor={setCursor}
            markers={markers}
            scenarios={spans}
          />
        </div>
      )}
      {(incidents.isError || runs.isError) && (
        <p className="px-4 py-2 text-small text-text-muted">
          Some investigation annotations could not be refreshed.
        </p>
      )}
      {(incidents.data?.next_cursor != null || runs.data?.next_cursor != null) && (
        <p className="px-4 py-2 text-small text-text-muted">
          Annotations cover the latest 100 incidents and scenario runs. Older items remain available
          in their lists.
        </p>
      )}
      {metric === null && (
        <EmptyState title="No measured metric.">
          No rule on {detail.key} measures a metric yet; rules appear after the first evaluation.
        </EmptyState>
      )}
      {metric !== null && series.isPending && <SkeletonRows rows={5} />}
      {series.isError && series.data === undefined && (
        <LoadError what="the metric history" query={series} />
      )}
      {series.data !== undefined && aligned && (
        <div className={staleClass(series.isError)}>
          <MetricChart
            series={series.data}
            thresholds={thresholds}
            markers={markers}
            cursor={cursor}
            onCursor={setCursor}
            leftInset={150}
          />
        </div>
      )}
    </Card>
  );
}
