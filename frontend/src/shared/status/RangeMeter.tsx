import type { Translator } from "@/shared/i18n/translate";
import { useT } from "@/shared/i18n/context";
import type { HealthState, KeyMetric } from "@/shared/api/types";
import { formatNumber, formatValue, metricLabel, unitLabel } from "@/shared/format/number";
import { formatUtcTime } from "@/shared/format/time";
import { Tooltip } from "@/shared/ui/Tooltip";

import { meterPosition, zones } from "./rangeScale";
import { STATE_LABEL, STATE_TEXT } from "./stateText";
import { StatusIndicator } from "./StatusIndicator";

function normalBound(metric: KeyMetric, t: Translator): string {
  const bound = metric.warning_threshold ?? metric.critical_threshold;
  return bound === null
    ? ""
    : t("normal below {value}", { value: formatValue(bound, metric.unit, t) });
}

function MeterDetails({ metric }: { metric: KeyMetric }) {
  const t = useT();
  const evaluated = new Date(metric.evaluated_at);
  return (
    <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5">
      <dt className="text-text-muted">{t("Value")}</dt>
      <dd className="data">
        {metric.value === null
          ? t("no samples in window")
          : formatValue(metric.value, metric.unit, t)}
      </dd>
      <dt className="text-text-muted">{t("Measure")}</dt>
      <dd className="data">
        {metric.aggregation}({metric.name}, {metric.window_seconds}&nbsp;s)
      </dd>
      <dt className="text-text-muted">{t("Evaluated")}</dt>
      <dd className="data">{formatUtcTime(evaluated)} UTC</dd>
      {metric.warning_threshold !== null && (
        <>
          <dt className="text-text-muted">{t("Warning threshold")}</dt>
          <dd className="data">{formatValue(metric.warning_threshold, metric.unit, t)}</dd>
        </>
      )}
      {metric.critical_threshold !== null && (
        <>
          <dt className="text-text-muted">{t("Critical threshold")}</dt>
          <dd className="data">{formatValue(metric.critical_threshold, metric.unit, t)}</dd>
        </>
      )}
      <dt className="text-text-muted">{t("Rule")}</dt>
      <dd className="data">
        {metric.rule.key} v{metric.rule.version}
      </dd>
      <dt className="text-text-muted">{t("Source")}</dt>
      <dd>{t("IPHI simulator")}</dd>
    </dl>
  );
}

const POINTER_TONE: Record<HealthState, string> = {
  healthy: "bg-text",
  unknown: "bg-text",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
};

/** Where the value sits against the normal range, before its number (§6.1). */
export function RangeMeter({ metric }: { metric: KeyMetric }) {
  const t = useT();
  const label = metricLabel(metric.name, t);
  const value = metric.value;
  const unit = unitLabel(metric.unit);
  const all = zones(metric);
  const normalEnd = all[0]?.end ?? 60;
  const ticks = all.slice(1).map((z, i) => ({ at: z.start, long: i === all.length - 2 }));

  // A stale value is no current evidence: no pointer, the last value stays in the tooltip.
  if (value === null || metric.state === "unknown") {
    return (
      <Tooltip focusable content={<MeterDetails metric={metric} />}>
        <span
          role="img"
          aria-label={
            value === null
              ? t("{label}: no samples in the last {seconds} s, {state}", {
                  label,
                  seconds: metric.window_seconds,
                  state: t.label(STATE_LABEL[metric.state]),
                })
              : t("{label}: no current value, {state}", {
                  label,
                  state: t.label(STATE_LABEL[metric.state]),
                })
          }
          className="flex items-center gap-3"
        >
          <span className="relative h-4 w-30 flex-none" aria-hidden="true">
            <span className="absolute inset-x-0 top-[7px] border-t-2 border-dashed border-border-strong" />
          </span>
          <span className="data w-18 text-right text-status-unknown">{t("no data")}</span>
        </span>
      </Tooltip>
    );
  }

  const { pct, beyond } = meterPosition(metric, value);
  const state = metric.state;
  const abnormal = state === "warning" || state === "critical";
  return (
    <Tooltip focusable content={<MeterDetails metric={metric} />}>
      <span
        role="meter"
        aria-label={label}
        aria-valuemin={metric.display_min}
        aria-valuemax={metric.display_max}
        aria-valuenow={Math.min(Math.max(value, metric.display_min), metric.display_max)}
        aria-valuetext={[
          formatValue(value, metric.unit, t),
          normalBound(metric, t),
          t.label(STATE_LABEL[state]),
        ]
          .filter((part) => part !== "")
          .join(", ")}
        className="flex items-center gap-3"
      >
        <span className="relative h-4 w-30 flex-none" aria-hidden="true">
          <span className="absolute inset-x-0 top-[7px] h-0.5 rounded-[1px] bg-border-strong opacity-70" />
          <span
            className="absolute top-[5px] left-0 h-1.5 rounded-[3px] bg-meter-normal"
            style={{ width: `${String(normalEnd)}%` }}
          />
          {ticks.map((tick) => (
            <span
              key={tick.at}
              className={`absolute w-px bg-text-muted ${tick.long ? "top-px h-3.5" : "top-[3px] h-2.5"}`}
              style={{ left: `${String(tick.at)}%` }}
            />
          ))}
          <span
            className={`absolute top-1 -ml-1 size-2 rounded-full shadow-[0_0_0_2px_var(--surface)] ${POINTER_TONE[state]}`}
            style={{ left: `${String(pct)}%` }}
          />
          {beyond && (
            <span className="absolute -top-0.5 -right-2.5 font-mono text-small leading-4 text-text-muted">
              ›
            </span>
          )}
        </span>
        <span
          className={`data inline-flex w-20 items-center justify-end gap-1 whitespace-nowrap ${STATE_TEXT[state]}`}
        >
          {abnormal && <StatusIndicator state={state} size="sm" />}
          {formatNumber(value, t)}
          {unit !== "" && <span className={abnormal ? "" : "text-text-muted"}>{unit}</span>}
        </span>
      </span>
    </Tooltip>
  );
}
