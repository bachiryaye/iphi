import type { MetricSeries } from "@/shared/api/types";
import { formatValue, unitLabel } from "@/shared/format/number";
import { formatUtcDateTime, formatUtcTime } from "@/shared/format/time";

import type { ChartOption } from "./EChart";

export interface Threshold {
  level: "warning" | "critical";
  value: number;
  /** What the threshold applies to, e.g. `p95 over 60 s`: rules judge aggregates, not samples. */
  basis: string;
}

export interface ChartMarker {
  at: string;
  label: string;
}

export interface EvidencePoint {
  sampleId: number;
  label: string;
}

export interface ChartColors {
  series: string;
  band: string;
  text: string;
  muted: string;
  grid: string;
  surface: string;
  highlight: string;
}

export interface MetricChartInput {
  series: MetricSeries;
  thresholds: readonly Threshold[];
  markers: readonly ChartMarker[];
  evidence: readonly EvidencePoint[];
  activeEvidence: number | null;
  colors: ChartColors;
}

type Point = [number, number | null];

// Past this many evidence points, only the selected one is labelled.
const MAX_EVIDENCE_LABELS = 6;

const ms = (iso: string) => new Date(iso).getTime();

/** Inserts a null at each gap start so the line breaks: a gap stays a gap (§7). */
function withGaps<T extends [number, ...(number | null)[]]>(
  points: T[],
  gaps: MetricSeries["gaps"],
  blank: (t: number) => T,
) {
  const breaks = gaps.map((g) => blank(ms(g.start)));
  return [...points, ...breaks].sort((a, b) => a[0] - b[0]);
}

const escapeHtml = (text: string) =>
  text.replace(/[&<>"']/g, (c) => `&#${String(c.charCodeAt(0))};`);

export function isProbe(series: MetricSeries): boolean {
  return series.metric_name === "up";
}

/** ECharts option for one metric on one Y axis, thresholds dashed and labelled (§7). */
export function metricChartOption(input: MetricChartInput): ChartOption {
  const { series, colors } = input;
  const unit = unitLabel(series.unit);
  const probe = isProbe(series);
  const byId = new Map(series.points.map((p) => [p.sample_id, p]));

  const base = {
    animation: false,
    useUTC: true,
    textStyle: { fontFamily: "IBM Plex Sans, system-ui, sans-serif", color: colors.muted },
    grid: { left: 56, right: 112, top: 24, bottom: 28 },
    xAxis: {
      type: "time",
      min: ms(series.window_start),
      max: ms(series.window_end),
      axisLine: { lineStyle: { color: colors.grid } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: {
        color: colors.muted,
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: 11,
        hideOverlap: true,
        formatter: (value: number) => formatUtcTime(new Date(value)).slice(0, 5),
      },
    },
    yAxis: {
      type: "value",
      name: probe ? "" : unit,
      nameTextStyle: { color: colors.muted, fontFamily: "IBM Plex Mono, monospace", fontSize: 11 },
      min: probe ? 0 : undefined,
      max: probe ? 1 : undefined,
      interval: probe ? 1 : undefined,
      splitLine: { lineStyle: { color: colors.grid, type: "solid" } },
      axisLabel: {
        color: colors.muted,
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: 11,
        formatter: probe ? (v: number) => (v >= 1 ? "up" : "down") : undefined,
      },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: colors.muted } },
      backgroundColor: colors.surface,
      borderColor: colors.grid,
      textStyle: { color: colors.text, fontSize: 12 },
      formatter: (params: { data: unknown[] }[]) => tooltipHtml(params, series),
    },
  };

  const thresholdLines = input.thresholds.map((t) => ({
    yAxis: t.value,
    lineStyle: {
      color: t.level === "critical" ? colors.text : colors.muted,
      type: t.level === "critical" ? [8, 4] : [3, 3],
      width: 1,
    },
    label: {
      formatter: `${t.level} ${formatValue(t.value, series.unit)}\n${t.basis}`,
      position: "end",
      color: colors.muted,
      fontSize: 11,
      lineHeight: 14,
    },
  }));
  const markerLines = input.markers.map((m) => ({
    xAxis: ms(m.at),
    lineStyle: { color: colors.muted, type: [3, 3], width: 1 },
    label: { formatter: m.label, position: "end", color: colors.text, fontSize: 11 },
  }));
  const markLine = {
    silent: true,
    symbol: "none",
    data: [...thresholdLines, ...markerLines],
  };
  const markPoint = {
    symbol: "circle",
    symbolSize: 8,
    data: input.evidence.flatMap((e) => {
      const point = byId.get(e.sampleId);
      if (point === undefined) return [];
      const active = input.activeEvidence === e.sampleId;
      const labelled = active || input.evidence.length <= MAX_EVIDENCE_LABELS;
      return [
        {
          coord: [ms(point.observed_at), point.value],
          itemStyle: {
            color: active ? colors.series : colors.text,
            borderColor: active ? colors.highlight : colors.surface,
            borderWidth: active ? 6 : 2,
          },
          label: {
            show: labelled,
            formatter: e.label,
            position: "top",
            color: active ? colors.series : colors.text,
            fontFamily: "IBM Plex Mono, monospace",
            fontSize: 11,
            fontWeight: 500,
          },
        },
      ];
    }),
  };

  if (series.mode === "raw") {
    const points: Point[] = series.points.map((p) => [ms(p.observed_at), p.value]);
    return {
      ...base,
      series: [
        {
          name: series.metric_name,
          type: "line",
          step: probe ? "end" : undefined,
          data: withGaps(points, series.gaps, (t) => [t, null]),
          connectNulls: false,
          showSymbol: points.length <= 120,
          symbolSize: 4,
          lineStyle: { color: colors.series, width: 2 },
          itemStyle: { color: colors.series },
          markLine,
          markPoint,
        },
      ],
    };
  }

  // Aggregated: the min-max range stays visible so a short peak is never averaged away (§7).
  type Bucket = [number, number | null, number | null];
  const buckets: Bucket[] = series.buckets.map((b) => [ms(b.bucket_start), b.min, b.max - b.min]);
  const banded = withGaps(buckets, series.gaps, (t) => [t, null, null]);
  const avg = withGaps<Point>(
    series.buckets.map((b) => [ms(b.bucket_start), b.avg]),
    series.gaps,
    (t) => [t, null],
  );
  return {
    ...base,
    series: [
      {
        name: "min",
        type: "line",
        data: banded.map(([t, min]) => [t, min]),
        stack: "range",
        connectNulls: false,
        showSymbol: false,
        lineStyle: { opacity: 0 },
        silent: true,
      },
      {
        name: "range",
        type: "line",
        data: banded.map(([t, , span]) => [t, span]),
        stack: "range",
        connectNulls: false,
        showSymbol: false,
        lineStyle: { opacity: 0 },
        areaStyle: { color: colors.band },
        silent: true,
      },
      {
        name: series.metric_name,
        type: "line",
        data: avg,
        connectNulls: false,
        showSymbol: false,
        lineStyle: { color: colors.series, width: 2 },
        itemStyle: { color: colors.series },
        markLine,
        markPoint,
      },
    ],
  };
}

function tooltipHtml(params: { data: unknown[] }[], series: MetricSeries): string {
  const first = params[0];
  if (first === undefined) return "";
  const t = first.data[0];
  if (typeof t !== "number") return "";
  const at = `<div style="font-family:IBM Plex Mono,monospace">${escapeHtml(formatUtcDateTime(new Date(t)))}</div>`;
  if (series.mode === "raw") {
    const value = first.data[1];
    if (typeof value !== "number") return `${at}<div>no data</div>`;
    const point = series.points.find((p) => ms(p.observed_at) === t);
    const meta =
      point === undefined
        ? ""
        : `<div>quality ${escapeHtml(point.quality)}, sample #${String(point.sample_id)}, simulated</div>`;
    return `${at}<div><b>${escapeHtml(formatValue(value, series.unit))}</b></div>${meta}`;
  }
  const bucket = series.buckets.find((b) => ms(b.bucket_start) === t);
  if (bucket === undefined) return `${at}<div>no data</div>`;
  return (
    `${at}<div>avg <b>${escapeHtml(formatValue(bucket.avg, series.unit))}</b></div>` +
    `<div>min ${escapeHtml(formatValue(bucket.min, series.unit))}, max ${escapeHtml(formatValue(bucket.max, series.unit))}</div>` +
    `<div>${String(bucket.count)} samples, quality ${escapeHtml(bucket.worst_quality)}, simulated</div>`
  );
}

/** Text equivalent of the chart for its accessible name (§9). */
export function chartSummary(series: MetricSeries, thresholds: readonly Threshold[]): string {
  const values =
    series.mode === "raw" ? series.points.map((p) => p.value) : series.buckets.map((b) => b.avg);
  const parts = [`${series.metric_name} for ${series.component_key}`];
  if (values.length === 0) {
    parts.push("no samples in this window");
  } else {
    const latest = values[values.length - 1] ?? 0;
    parts.push(
      `latest ${formatValue(latest, series.unit)}`,
      `min ${formatValue(Math.min(...values), series.unit)}`,
      `max ${formatValue(Math.max(...values), series.unit)}`,
    );
  }
  for (const t of thresholds)
    parts.push(`${t.level} ${formatValue(t.value, series.unit)} (${t.basis})`);
  if (series.gaps.length > 0) {
    parts.push(
      `${String(series.gaps.length)} gap${series.gaps.length === 1 ? "" : "s"} without data`,
    );
  }
  return parts.join(", ");
}
