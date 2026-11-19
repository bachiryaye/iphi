import { useT } from "@/shared/i18n/context";
import { Branch } from "@carbon/icons-react";
import { Link } from "react-router";

import type { Component, HealthState, Platform } from "@/shared/api/types";
import { formatDuration } from "@/shared/format/time";
import { usePlatformClock } from "@/shared/hooks/usePlatformNow";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { STATE_LABEL, STATE_TEXT } from "@/shared/status/stateText";
import { StatusIndicator } from "@/shared/status/StatusIndicator";
import { Timestamp } from "@/shared/status/Timestamp";

const ORDER: readonly HealthState[] = ["healthy", "warning", "critical", "unknown"];

function Since({ iso }: { iso: string }) {
  const t = useT();
  const now = usePlatformClock();
  return (
    <span>
      {t("since")} <Timestamp iso={iso} />{" "}
      <span className="text-text-muted">
        {t("for")} {formatDuration((now.getTime() - new Date(iso).getTime()) / 1000)}
      </span>
    </span>
  );
}

interface PlatformHealthCardProps {
  platform: Platform;
  components: readonly Component[];
}

/** Answers "is everything fine, if not where and since when" with the API's own rationale. */
export function PlatformHealthCard({ platform, components }: PlatformHealthCardProps) {
  const t = useT();
  const health = platform.health;
  const impacted = components.filter((c) => c.impacted_by.length > 0);
  return (
    <div className="flex flex-col gap-3.5 px-4 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <HealthBadge health={health} size="lg" />
        {health.since !== null && <Since iso={health.since} />}
      </div>
      <p>{health.rationale}</p>
      {health.decided_by.length > 0 && (
        <p className="flex flex-wrap gap-x-2 text-small text-text-muted">
          {t("Open the component behind this state:")}{" "}
          {health.decided_by.map((ref) => (
            <Link key={ref.id} to={`/components/${ref.id}`} className="text-link">
              {ref.key}
            </Link>
          ))}
        </p>
      )}
      <ul
        aria-label={t("Components by state")}
        className="grid grid-cols-4 rounded-control border border-border"
      >
        {ORDER.map((state) => {
          const count = health.counts[state];
          return (
            <li
              key={state}
              className="flex flex-col gap-0.5 border-l border-border px-3 py-2 first:border-l-0"
            >
              <span className="inline-flex items-center gap-1.5 text-small text-text-muted">
                <StatusIndicator state={state} size="sm" />
                {t.label(STATE_LABEL[state])}
              </span>
              <span
                className={`font-mono text-kpi font-medium ${count === 0 ? "text-text-muted" : STATE_TEXT[state]}`}
              >
                {count}
              </span>
            </li>
          );
        })}
      </ul>
      {impacted.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-text-muted">
          <Branch size={16} aria-hidden="true" />
          {impacted.length === 1
            ? t("1 component impacted:")
            : t("{count} components impacted:", { count: impacted.length })}
          {impacted.map((c) => (
            <Link key={c.id} to={`/components/${c.id}`} className="text-link whitespace-nowrap">
              {c.key}
            </Link>
          ))}
        </p>
      )}
      {health.stale && <p className="text-small text-text-muted">{health.stale_reason}</p>}
    </div>
  );
}
