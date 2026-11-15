const compact = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });
const precise = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 });

/** Units as the catalog stores them, as an operator reads them. */
const UNIT_LABEL: Record<string, string> = { count: "", bool: "" };

export function unitLabel(unit: string | null | undefined): string {
  if (unit == null) return "";
  return UNIT_LABEL[unit] ?? unit;
}

export function formatNumber(value: number): string {
  return Math.abs(value) < 1 && value !== 0 ? precise.format(value) : compact.format(value);
}

/** `42 ms`, `31 %`, `8`: the value with its unit, separated by a non-breaking space. */
export function formatValue(value: number, unit: string | null | undefined): string {
  const label = unitLabel(unit);
  return label === "" ? formatNumber(value) : `${formatNumber(value)}\u00a0${label}`;
}

const METRIC_LABEL: Record<string, string> = {
  up: "probe result",
  probe_latency_ms: "probe latency",
  data_age_s: "data age",
  error_count: "errors",
  cpu_pct: "cpu",
  mem_pct: "memory",
  queue_depth: "queue depth",
};

export const metricLabel = (name: string): string =>
  METRIC_LABEL[name] ?? name.replaceAll("_", " ");
