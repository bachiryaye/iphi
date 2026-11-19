import { useT } from "@/shared/i18n/context";
import { DataTable } from "@carbon/icons-react";
import { lazy, Suspense, useMemo, useState } from "react";

import type { MetricSeries } from "@/shared/api/types";
import { formatValue } from "@/shared/format/number";
import { useThemeVersion, token } from "@/shared/hooks/useThemeVersion";
import { Timestamp } from "@/shared/status/Timestamp";
import { Button } from "@/shared/ui/Button";

import {
  type ChartMarker,
  chartSummary,
  type EvidencePoint,
  metricChartOption,
  type Threshold,
} from "./metricChart";

interface MetricChartProps {
  series: MetricSeries;
  thresholds?: readonly Threshold[];
  markers?: readonly ChartMarker[];
  evidence?: readonly EvidencePoint[];
  activeEvidence?: number | null;
  height?: number;
  cursor?: number | null;
  onCursor?: (at: number | null) => void;
  leftInset?: number;
}

// ECharts is most of the bundle and only the Component and Incident views draw charts.
const EChart = lazy(() => import("./EChart").then((module) => ({ default: module.EChart })));

const TABLE_ROWS = 60;
// Stable defaults: a fresh [] per render would rebuild the chart option every time.
const NONE: readonly never[] = [];

function readColors() {
  return {
    series: token("--accent"),
    band: token("--highlight"),
    text: token("--text"),
    muted: token("--text-muted"),
    grid: token("--border"),
    surface: token("--surface"),
    highlight: token("--highlight"),
  };
}

function SeriesTable({ series }: { series: MetricSeries }) {
  const t = useT();
  const raw = series.mode === "raw";
  const empty = raw ? series.points.length === 0 : series.buckets.length === 0;
  return (
    <div className="max-h-80 overflow-y-auto border-t border-border">
      <table className="data-table">
        <caption className="sr-only">
          {t("Latest values of")} {series.metric_name}
        </caption>
        <thead>
          <tr>
            <th scope="col">{t("Time (UTC)")}</th>
            <th scope="col" className="num">
              {raw ? t("Value") : t("Average")}
            </th>
            {!raw && (
              <th scope="col" className="num">
                {t("Min – max")}
              </th>
            )}
            <th scope="col">{raw ? t("Quality") : t("Samples")}</th>
          </tr>
        </thead>
        <tbody>
          {raw
            ? series.points
                .slice(-TABLE_ROWS)
                .reverse()
                .map((p) => (
                  <tr key={p.sample_id}>
                    <td>
                      <Timestamp iso={p.observed_at} />
                    </td>
                    <td className="num data">{formatValue(p.value, series.unit, t)}</td>
                    <td className="text-text-muted">{p.quality}</td>
                  </tr>
                ))
            : series.buckets
                .slice(-TABLE_ROWS)
                .reverse()
                .map((b) => (
                  <tr key={b.bucket_start}>
                    <td>
                      <Timestamp iso={b.bucket_start} />
                    </td>
                    <td className="num data">{formatValue(b.avg, series.unit, t)}</td>
                    <td className="num data">
                      {formatValue(b.min, series.unit, t)} – {formatValue(b.max, series.unit, t)}
                    </td>
                    <td className="data text-text-muted">{b.count}</td>
                  </tr>
                ))}
        </tbody>
      </table>
      {empty && <p className="px-4 py-3 text-text-muted">{t("No samples in this window.")}</p>}
      {series.gaps.length > 0 && (
        <p className="border-t border-border px-4 py-2.5 text-small text-text-muted">
          {t("Gaps without data:")}{" "}
          {series.gaps.map((g, i) => (
            <span key={g.start}>
              {i > 0 && ", "}
              <Timestamp iso={g.start} suffix={false} /> {t("to")} <Timestamp iso={g.end} />
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

/** One stored metric on one axis, with its text equivalent one click away (§7, §9). */
export function MetricChart({
  series,
  thresholds = NONE,
  markers = NONE,
  evidence = NONE,
  activeEvidence = null,
  height = 240,
  cursor = null,
  onCursor,
  leftInset = 56,
}: MetricChartProps) {
  const t = useT();
  const theme = useThemeVersion();
  const [table, setTable] = useState(false);
  const option = useMemo(
    () =>
      metricChartOption(
        {
          series,
          thresholds,
          markers,
          evidence,
          activeEvidence,
          colors: readColors(),
          leftInset,
        },
        t,
      ),
    // The theme only changes the tokens read inside.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [series, thresholds, markers, evidence, activeEvidence, theme, leftInset, t],
  );
  const summary = chartSummary(series, thresholds, t);
  return (
    <figure className="flex flex-col">
      <div role="img" aria-label={summary} className="px-2 pt-1">
        <Suspense fallback={<div className="skeleton" style={{ height }} />}>
          <EChart option={option} height={height} cursor={cursor} onCursor={onCursor} />
        </Suspense>
      </div>
      <figcaption className="flex flex-wrap items-center gap-3 px-4 pb-3 text-small text-text-muted">
        <span>
          {series.mode === "raw"
            ? t("Raw 5 s samples")
            : t("Averages per {seconds} s, shaded min to max", {
                seconds: series.bucket_s ?? 0,
              })}{" "}
          {t("; thresholds apply to the rule's aggregate.")}
        </span>
        <Button
          variant="quiet"
          className="ml-auto h-7"
          aria-expanded={table}
          onClick={() => {
            setTable((open) => !open);
          }}
          icon={<DataTable size={16} aria-hidden="true" />}
        >
          {table ? t("Hide table") : t("View as table")}
        </Button>
      </figcaption>
      {table && <SeriesTable series={series} />}
    </figure>
  );
}
