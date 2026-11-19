import { useT } from "@/shared/i18n/context";
import { useMemo } from "react";

import { useHealthRules, useMetricSeries } from "@/shared/api/queries";
import type { IncidentDetail } from "@/shared/api/types";
import { MetricChart } from "@/shared/charts/MetricChart";
import type { EvidencePoint } from "@/shared/charts/metricChart";
import { metricLabel } from "@/shared/format/number";
import { usePlatformNow } from "@/shared/hooks/usePlatformNow";
import { Card } from "@/shared/ui/Card";
import { LoadError, SkeletonRows } from "@/shared/ui/QueryStates";

const BEFORE_MS = 5 * 60_000;
const AFTER_MS = 2 * 60_000;
const MAX_MS = 24 * 3600_000;

/** The triggering rule's signal around the incident, with its evidence points (§6.4). */
export function IncidentSignal({
  incident,
  activeSample,
}: {
  incident: IncidentDetail;
  activeSample: number | null;
}) {
  const t = useT();
  const rules = useHealthRules();
  const platformNow = usePlatformNow(60_000);
  const ruleKey = incident.condition[0]?.rule.key;
  const metric = rules.data?.items.find((r) => r.key === ruleKey)?.metric_name ?? null;
  const opened = new Date(incident.opened_at).getTime();
  const endMs =
    incident.resolved_at !== null
      ? new Date(incident.resolved_at).getTime() + AFTER_MS
      : (platformNow?.getTime() ?? null);

  const request = useMemo(() => {
    if (metric === null || endMs === null) return null;
    return {
      componentId: incident.component.id,
      metricName: metric,
      from: new Date(Math.max(opened - BEFORE_MS, endMs - MAX_MS)).toISOString(),
      to: new Date(endMs).toISOString(),
    };
  }, [incident.component.id, metric, opened, endMs]);
  const series = useMetricSeries(request);

  // Supporting evaluations can cite a whole 300 s window: only trigger and recovery samples,
  // plus the one a chip selected, are drawn so the labels stay readable.
  const evidence = useMemo<EvidencePoint[]>(
    () =>
      incident.evidence.flatMap((e) =>
        e.sample !== null &&
        e.sample.metric_name === metric &&
        e.component?.id === incident.component.id &&
        (e.role === "trigger" || e.role === "recovery" || e.sample.id === activeSample)
          ? [{ sampleId: e.sample.id, label: e.label }]
          : [],
      ),
    [incident, metric, activeSample],
  );
  const markers = useMemo(
    () => [
      { at: incident.opened_at, label: `${incident.reference} ${t("Opened")}` },
      ...(incident.resolved_at === null
        ? []
        : [{ at: incident.resolved_at, label: t("Resolved") }]),
    ],
    [incident, t],
  );

  if (rules.data !== undefined && metric === null) return null;
  return (
    <Card
      title={
        metric === null
          ? t("Signal")
          : `Signal: ${incident.component.key} ${metricLabel(metric, t)}`
      }
      titleId="signal-title"
      busy={series.isPending}
      meta={<span>{ruleKey ?? ""}, UTC</span>}
    >
      {series.isPending && <SkeletonRows rows={4} />}
      {series.isError && series.data === undefined && (
        <LoadError what={t("the signal")} query={series} />
      )}
      {series.data !== undefined && (
        <MetricChart
          series={series.data}
          markers={markers}
          evidence={evidence}
          activeEvidence={activeSample}
          height={200}
        />
      )}
    </Card>
  );
}
