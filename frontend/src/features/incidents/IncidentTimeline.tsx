import type { Translator } from "@/shared/i18n/translate";
import { useT } from "@/shared/i18n/context";
import {
  Branch,
  Chat,
  CheckmarkOutline,
  ChevronDown,
  DocumentView,
  Layers,
  Renew,
  UserFollow,
} from "@carbon/icons-react";
import { useState } from "react";

import type { IncidentEvent, IncidentSeverity } from "@/shared/api/types";
import { formatUtcTime } from "@/shared/format/time";
import { StatusIndicator } from "@/shared/status/StatusIndicator";
import { Timestamp } from "@/shared/status/Timestamp";

import { groupTimeline } from "./timeline";

const str = (value: unknown): string => (typeof value === "string" ? value : "");
const isSeverity = (value: unknown): value is IncidentSeverity =>
  value === "warning" || value === "critical";

function describe(event: IncidentEvent, t: Translator): string {
  const p = event.payload;
  switch (event.type) {
    case "opened":
      return t("Opened as {severity} ({rule})", {
        severity: t.label(str(p.severity)),
        rule: str(p.rule_key),
      });
    case "severity_changed":
      return t("Severity {from} to {to} ({rule})", {
        from: t.label(str(p.from)),
        to: t.label(str(p.to)),
        rule: str(p.rule_key),
      });
    case "acknowledged":
      return t("Acknowledged");
    case "commented":
      return t("Comment added");
    case "resolved":
      return str(p.resolution) === "auto_recovered"
        ? t("Resolved: condition cleared")
        : str(p.resolution) === "reset"
          ? t("Resolved by simulation reset")
          : t("Resolved manually");
    case "reopened":
      return t("Reopened as {severity}", { severity: t.label(str(p.severity)) });
    case "reclassified":
      return t("Reclassified {from} to {to}", {
        from: t.label(str(p.from)),
        to: t.label(str(p.to)),
      });
    case "downstream_suppressed":
      return t("{component} {failure} attached here, no new incident", {
        component: str(p.component_key),
        failure: t.label(str(p.failure_class).replaceAll("_", " ")),
      });
    case "diagnostic_added":
      return t("{kind} diagnosis added", {
        kind: t.label(str(p.kind) === "llm" ? "AI" : "Deterministic"),
      });
    default:
      return event.type;
  }
}

function Icon({ event }: { event: IncidentEvent }) {
  const severity = event.payload.severity ?? event.payload.to;
  if (
    (event.type === "opened" || event.type === "severity_changed" || event.type === "reopened") &&
    isSeverity(severity)
  ) {
    return <StatusIndicator state={severity} size="md" />;
  }
  const props = { size: 16, "aria-hidden": true } as const;
  switch (event.type) {
    case "acknowledged":
      return <UserFollow {...props} />;
    case "commented":
      return <Chat {...props} />;
    case "resolved":
      return <CheckmarkOutline {...props} />;
    case "reopened":
      return <Renew {...props} />;
    case "downstream_suppressed":
      return <Branch {...props} />;
    case "diagnostic_added":
      return <DocumentView {...props} />;
    default:
      return <Layers {...props} />;
  }
}

function Row({
  time,
  icon,
  children,
}: {
  time: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <li className="relative grid grid-cols-[64px_16px_minmax(0,1fr)] gap-2.5 pb-3.5 last:pb-0 [&:not(:last-child)]:after:absolute [&:not(:last-child)]:after:top-[22px] [&:not(:last-child)]:after:bottom-0.5 [&:not(:last-child)]:after:left-[81.5px] [&:not(:last-child)]:after:w-px [&:not(:last-child)]:after:bg-border">
      <Timestamp suffix={false} className="text-small text-text-muted" iso={time} />
      <span className="mt-0.5 text-text-muted">{icon}</span>
      <div className="min-w-0">{children}</div>
    </li>
  );
}

function Occurrences({ events }: { events: IncidentEvent[] }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const first = events[0];
  const last = events[events.length - 1];
  if (first === undefined || last === undefined) return null;
  return (
    <Row time={first.occurred_at} icon={<Layers size={16} aria-hidden="true" />}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => !v);
        }}
        className="inline-flex cursor-pointer items-center gap-1.5 text-left"
      >
        {events.length === 1
          ? t("1 occurrence")
          : t("{count} occurrences grouped", { count: events.length })}
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={`text-text-muted transition-transform duration-150 ${open ? "rotate-180" : ""}`}
        />
      </button>
      <p className="text-small text-text-muted">
        {formatUtcTime(new Date(first.occurred_at))} {t("to")}{" "}
        {formatUtcTime(new Date(last.occurred_at))}
        {t(", same fingerprint")}
      </p>
      {open && (
        <ul className="mt-1 text-small text-text-muted">
          {events.map((e) => (
            <li key={e.id}>
              <Timestamp
                suffix={false}
                className="text-small text-text-muted"
                iso={e.occurred_at}
              />{" "}
              {str(e.payload.rule_key)} {t("evaluation #")}
              {String(e.payload.evaluation_id ?? "")}
            </li>
          ))}
        </ul>
      )}
    </Row>
  );
}

/** Chronological, oldest first, in UTC (§6.4, IncidentTimeline). */
export function IncidentTimeline({ events }: { events: readonly IncidentEvent[] }) {
  const t = useT();
  const entries = groupTimeline(events);
  return (
    <ol className="px-4 py-3">
      {entries.map((entry) =>
        entry.kind === "occurrences" ? (
          <Occurrences key={`o-${String(entry.events[0]?.id)}`} events={entry.events} />
        ) : (
          <Row
            key={entry.event.id}
            time={entry.event.occurred_at}
            icon={<Icon event={entry.event} />}
          >
            <p>{describe(entry.event, t)}</p>
            <p className="text-small text-text-muted">{entry.event.actor_label}</p>
            {typeof entry.event.payload.comment === "string" && (
              <p className="mt-0.5 text-small">“{entry.event.payload.comment}”</p>
            )}
          </Row>
        ),
      )}
    </ol>
  );
}
