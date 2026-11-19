import { english, type Translator } from "@/shared/i18n/translate";

import type { MetricSeries } from "@/shared/api/types";
import { formatValue } from "@/shared/format/number";
const ms = (iso: string) => new Date(iso).getTime();

export function cursorValue(
  series: MetricSeries | undefined,
  at: number,
  t: Translator = english,
): string {
  if (series === undefined || series.gaps.some((g) => ms(g.start) <= at && at < ms(g.end)))
    return t("no data");
  if (series.mode === "raw") {
    const point = series.points.findLast(
      (p) => ms(p.observed_at) <= at && at - ms(p.observed_at) < 5000,
    );
    return point?.quality === "good" ? formatValue(point.value, series.unit, t) : t("no data");
  }
  const bucket = series.buckets.find(
    (b) => ms(b.bucket_start) <= at && at < ms(b.bucket_start) + (series.bucket_s ?? 0) * 1000,
  );
  return bucket?.avg == null
    ? t("no data")
    : t("{value} average", { value: formatValue(bucket.avg, series.unit, t) });
}
