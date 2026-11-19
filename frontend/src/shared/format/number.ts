import { english, type Translator } from "@/shared/i18n/translate";

const formats = {
  en: [
    new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 }),
    new Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 }),
  ],
  fr: [
    new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }),
    new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 }),
  ],
} as const;

/** Units as the catalog stores them, as an operator reads them. */
const UNIT_LABEL: Record<string, string> = { count: "", bool: "" };

export function unitLabel(unit: string | null | undefined): string {
  if (unit == null) return "";
  return UNIT_LABEL[unit] ?? unit;
}

export function formatNumber(value: number, t: Translator = english): string {
  const [compact, precise] = formats[t.language];
  return Math.abs(value) < 1 && value !== 0 ? precise.format(value) : compact.format(value);
}

/** `42 ms`, `31 %`, `8`: the value with its unit, separated by a non-breaking space. */
export function formatValue(
  value: number,
  unit: string | null | undefined,
  t: Translator = english,
): string {
  const label = unitLabel(unit);
  return label === "" ? formatNumber(value, t) : `${formatNumber(value, t)}\u00a0${label}`;
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

export const metricLabel = (name: string, t: Translator = english): string =>
  t.label(METRIC_LABEL[name] ?? name.replaceAll("_", " "));
