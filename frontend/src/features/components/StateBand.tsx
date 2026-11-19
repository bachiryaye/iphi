import { useT } from "@/shared/i18n/context";
import { useState } from "react";

import { useEvaluationHistory } from "@/shared/api/queries";
import type { HistoryLane, MetricSeries, StateHistory } from "@/shared/api/types";
import type { ChartMarker } from "@/shared/charts/metricChart";
import { cursorValue } from "./cursorValue";
import { formatUtcDateTime } from "@/shared/format/time";
import { Timestamp } from "@/shared/status/Timestamp";
import { Button } from "@/shared/ui/Button";
import { LoadError } from "@/shared/ui/QueryStates";

import "./state-band.css";
import { useEvaluationSelection, type EvaluationSelection } from "./useEvaluationSelection";

interface ScenarioSpan {
  from: string;
  to: string;
  label: string;
}
interface Props {
  history: StateHistory;
  series: MetricSeries | undefined;
  cursor: number | null;
  onCursor: (at: number | null) => void;
  markers: readonly ChartMarker[];
  scenarios: readonly ScenarioSpan[];
}

const ms = (iso: string) => new Date(iso).getTime();
const title = (state: string) => state.charAt(0).toUpperCase() + state.slice(1);

function segmentAt(lane: HistoryLane, at: number) {
  return lane.segments.find((s) => ms(s.from) <= at && at < ms(s.to));
}

function Evaluations({ history, filter }: { history: StateHistory; filter: EvaluationSelection }) {
  const t = useT();
  const query = useEvaluationHistory({
    componentId: history.component.id,
    from: filter.from,
    to: filter.to,
    ...(filter.lane === "component" ? {} : { ruleKey: filter.lane }),
  });
  return (
    <div className="border-t border-border">
      <p className="px-4 py-2 text-small text-text-muted">
        {t("Stored evaluations ·")} {filter.lane} · <Timestamp iso={filter.from} /> {t("to")}{" "}
        <Timestamp iso={filter.to} /> {t("· newest 50")}
      </p>
      {query.isPending && (
        <p className="p-4" role="status">
          {t("Loading evaluations…")}
        </p>
      )}
      {query.isError && <LoadError what={t("recorded evaluations")} query={query} />}
      {query.data !== undefined && (
        <div className="max-h-64 overflow-auto">
          <table className="data-table">
            <caption className="sr-only">{t("Filtered stored evaluations")}</caption>
            <thead>
              <tr>
                <th scope="col">UTC</th>
                <th scope="col">{t("Rule")}</th>
                <th scope="col">{t("State")}</th>
                <th scope="col">{t("Explanation / proof")}</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((e) => (
                <tr key={e.id}>
                  <td>
                    <Timestamp iso={e.evaluated_at} />
                  </td>
                  <td className="data">
                    {e.rule.key} v{String(e.rule.version)}
                  </td>
                  <td>{t.label(title(e.state))}</td>
                  <td>
                    {e.explanation} {t("· evaluation #")}
                    {String(e.id)} · {e.evidence.sample_ids.length} {t("samples,")}{" "}
                    {e.evidence.log_ids.length} {t("logs")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {query.data.items.length === 0 && (
            <p className="p-4 text-text-muted">
              {t(
                "No evaluation in this interval. The band may carry an earlier proof until the next recorded watermark.",
              )}
            </p>
          )}
          {query.data.next_cursor !== null && (
            <p className="p-4 text-small text-text-muted">
              {t("More evaluations exist; select a narrower interval to inspect them.")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function StateBand({ history, series, cursor, onCursor, markers, scenarios }: Props) {
  const t = useT();
  const [table, setTable] = useState(false);
  const start = ms(history.from),
    end = ms(history.to),
    duration = end - start;
  const lanes = [history.component_lane, ...history.rules];
  const {
    selection: filter,
    choose,
    clear,
  } = useEvaluationSelection(lanes.map((lane) => lane.key));
  const percent = (at: number) => ((at - start) / duration) * 100;
  const inspect = cursor === null ? null : Math.min(end - 1, Math.max(start, cursor));
  const description =
    inspect === null
      ? t(
          "Use Left and Right arrows to inspect time; Shift moves one minute. Home, End and Escape are available.",
        )
      : `${formatUtcDateTime(new Date(inspect))}. ${lanes.map((lane) => `${lane.key}: ${t.label(title(segmentAt(lane, inspect)?.state ?? "unknown"))}`).join(". ")}. ${t("Metric")}: ${cursorValue(series, inspect, t)}.`;
  return (
    <section aria-label={t("Recorded health history")} className="border-b border-border">
      <div className="flex flex-wrap items-center gap-2 px-4 py-2">
        <h3 className="font-medium">{t("Recorded states")}</h3>
        <span className="text-small text-text-muted">
          {t("Neutral Healthy · hatched Unknown · server evaluations")}
        </span>
        <Button
          variant="quiet"
          className="ml-auto"
          aria-expanded={table}
          onClick={() => {
            setTable((v) => !v);
          }}
        >
          {t("View states as table")}
        </Button>
      </div>
      <div className="overflow-x-auto px-2">
        <div className="min-w-[480px]">
          <div
            className="relative cursor-crosshair py-2"
            onPointerMove={(event) => {
              const box = event.currentTarget.getBoundingClientRect();
              const offset = event.clientX - box.left - 150;
              const width = box.width - 150 - 112;
              if (offset >= 0 && offset <= width) onCursor(start + (offset / width) * duration);
            }}
            onPointerLeave={() => {
              onCursor(null);
            }}
          >
            {lanes.map((lane, index) => (
              <div
                key={lane.key}
                className="mb-0.5 grid grid-cols-[150px_minmax(0,1fr)_112px] items-center"
              >
                <span className="truncate pr-2 text-small data">
                  {lane.key === "component"
                    ? history.component.key
                    : `${lane.key} v${lane.versions.join(",")}`}
                </span>
                <div
                  className="relative overflow-hidden border-y border-border"
                  style={{ height: index === 0 ? 20 : 14 }}
                >
                  {lane.segments.map((s) => (
                    <button
                      type="button"
                      tabIndex={-1}
                      key={s.from}
                      className={`state-segment state-${s.state} ${s.contains_unknown && s.state !== "unknown" ? "has-unknown" : ""}`}
                      style={{
                        left: `${String(percent(ms(s.from)))}%`,
                        width: `${String(percent(ms(s.to)) - percent(ms(s.from)))}%`,
                        minWidth: 2,
                      }}
                      title={`${lane.key}: ${t.label(title(s.state))}; ${s.from} ${t("to")} ${s.to}${s.contains_unknown ? t("; includes Unknown coverage") : ""}`}
                      onClick={() => {
                        choose(lane.key, s);
                      }}
                    >
                      {index === 0 &&
                        s.state !== "healthy" &&
                        (ms(s.to) - ms(s.from)) / duration > 0.15 && (
                          <span className="px-1 text-small">{t.label(title(s.state))}</span>
                        )}
                    </button>
                  ))}
                  {inspect !== null && (
                    <span
                      className="pointer-events-none absolute inset-y-0 z-10 w-px bg-text"
                      style={{ left: `${String(percent(inspect))}%` }}
                    />
                  )}
                </div>
                <span className="pl-2 text-small text-text-muted">
                  {lane.aggregated ? t("peak bins") : ""}
                </span>
              </div>
            ))}
            <div className="relative ml-[150px] mr-[112px] h-5" aria-hidden="true">
              {markers
                .filter((m) => ms(m.at) >= start && ms(m.at) < end)
                .map((m) => (
                  <span
                    key={`${m.at}-${m.label}`}
                    className="absolute top-0 text-small text-text-muted"
                    style={{ left: `${String(percent(ms(m.at)))}%` }}
                    title={m.label}
                  >
                    ▼
                  </span>
                ))}
            </div>
          </div>
          <div className="ml-[150px] mr-[112px] pb-2">
            <input
              type="range"
              min={start}
              max={end - 1}
              step={1}
              value={inspect ?? start}
              aria-label={t("History time inspector")}
              aria-valuetext={description}
              className="h-5 w-full accent-accent"
              onChange={(event) => {
                onCursor(Number(event.target.value));
              }}
              onKeyDown={(event) => {
                const step = event.shiftKey ? 60000 : 15000;
                const current = inspect ?? start;
                const next =
                  event.key === "ArrowLeft"
                    ? current - step
                    : event.key === "ArrowRight"
                      ? current + step
                      : event.key === "Home"
                        ? start
                        : event.key === "End"
                          ? end - 1
                          : undefined;
                if (next !== undefined) {
                  event.preventDefault();
                  onCursor(Math.max(start, Math.min(end - 1, next)));
                }
                if (event.key === "Escape") onCursor(null);
              }}
            />
          </div>
          {scenarios.slice(0, 6).map((run) => (
            <div
              key={run.label}
              className="ml-[150px] mr-[112px] mb-1"
              title={`${run.from} ${t("to")} ${run.to}`}
            >
              <div
                className="truncate border-x border-t border-border-strong px-1 text-small text-text-muted"
                style={{
                  marginLeft: `${String(Math.max(0, percent(ms(run.from))))}%`,
                  width: `${String(Math.min(100, percent(ms(run.to))) - Math.max(0, percent(ms(run.from))))}%`,
                }}
              >
                {run.label}
              </div>
            </div>
          ))}
        </div>
      </div>
      {scenarios.length > 0 && (
        <details className="px-4 py-2 text-small text-text-muted">
          <summary className="cursor-pointer">
            {t("Scenario runs in this window (")}
            {scenarios.length}){scenarios.length > 6 ? t(" · latest six drawn") : ""}
          </summary>
          <ul className="mt-2 flex flex-col gap-1">
            {scenarios.map((run) => (
              <li key={run.label}>
                {run.label} · <Timestamp iso={run.from} /> {t("to")} <Timestamp iso={run.to} />
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="min-h-12 px-4 py-2 text-small text-text-muted" aria-live="off">
        {description}
      </p>
      {markers.length > 0 && (
        <p className="px-4 pb-2 text-small text-text-muted">
          {t("Incident markers (latest labeled on the chart):")}{" "}
          {markers.map((m) => (
            <span key={`${m.at}-${m.label}`}>
              {m.label} <Timestamp iso={m.at} />;{" "}
            </span>
          ))}
        </p>
      )}
      {table && (
        <div className="max-h-72 overflow-auto border-t border-border">
          <table className="data-table">
            <caption className="sr-only">{t("Recorded state transitions")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("Lane / version")}</th>
                <th scope="col">{t("From (UTC)")}</th>
                <th scope="col">{t("To (UTC)")}</th>
                <th scope="col">{t("State")}</th>
                <th scope="col">{t("Evaluations")}</th>
              </tr>
            </thead>
            <tbody>
              {lanes.flatMap((lane) =>
                lane.segments.map((s) => (
                  <tr key={`${lane.key}-${s.from}`}>
                    <th scope="row" className="data">
                      {lane.key} {lane.versions.join(",")}
                    </th>
                    <td>
                      <Timestamp iso={s.from} />
                    </td>
                    <td>
                      <Timestamp iso={s.to} />
                    </td>
                    <td>
                      {t.label(title(s.state))}
                      {s.contains_unknown && s.state !== "unknown"
                        ? t(" (also Unknown coverage)")
                        : ""}
                      {lane.aggregated ? t(" · peak bin") : ""}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="text-link"
                        onClick={() => {
                          choose(lane.key, s);
                        }}
                      >
                        {s.evaluation_ids.length === 0
                          ? t("Inspect interval")
                          : t("Inspect #{ids}", { ids: s.evaluation_ids.join(", #") })}
                      </button>
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      )}
      {filter !== null && (
        <>
          <Button
            variant="quiet"
            className="mx-4 mb-2"
            onClick={() => {
              clear();
            }}
          >
            {t("Clear evaluation filter")}
          </Button>
          <Evaluations history={history} filter={filter} />
        </>
      )}
    </section>
  );
}
