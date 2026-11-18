import { ChevronRight } from "@carbon/icons-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";

import { useCitedEvidence, useIncident } from "@/shared/api/queries";
import type { IncidentDetail } from "@/shared/api/types";
import { IncidentStatusLabel } from "@/shared/status/IncidentStatus";
import { SimTag } from "@/shared/status/SimTag";
import { StatusBadge } from "@/shared/status/StatusBadge";
import { Timestamp } from "@/shared/status/Timestamp";
import { Card } from "@/shared/ui/Card";
import { CopyButton } from "@/shared/ui/CopyButton";
import { LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

import { type EvidenceFocus } from "./DiagnosisCard";
import { DiagnosisPanel } from "./DiagnosisPanel";
import { EvidenceChain } from "./EvidenceChain";
import { IncidentActions } from "./IncidentActions";
import { IncidentSignal } from "./IncidentSignal";
import { InvestigationTimeline } from "./InvestigationTimeline";
import { humanize } from "@/shared/format/labels";

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-2 border-l border-border px-4 first:border-l-0 first:pl-0">
      <dt className="text-small text-text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Header({ incident }: { incident: IncidentDetail }) {
  return (
    <header className="flex flex-col gap-3">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-small text-text-muted">
        <Link to="/incidents" className="text-link">
          Incidents
        </Link>
        <ChevronRight size={16} aria-hidden="true" />
        <span className="data text-text">{incident.reference}</span>
      </nav>
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-6 gap-y-3 max-xl:grid-cols-1">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <StatusBadge state={incident.severity} size="lg" />
          <h1 className="text-display font-semibold">
            <span className="mr-2 font-mono text-heading font-medium text-text-muted">
              {incident.reference}
            </span>
            {incident.title}
          </h1>
        </div>
        <IncidentActions incident={incident} />
      </div>
      <dl className="flex flex-wrap items-center gap-y-1">
        <Fact label="Status">
          <IncidentStatusLabel status={incident.status} acknowledgedBy={incident.acknowledged_by} />
        </Fact>
        <Fact label="Failure class">{humanize(incident.failure_class)}</Fact>
        <Fact label="Opened">
          <Timestamp iso={incident.opened_at} />{" "}
          <span className="text-text-muted">
            (<Timestamp iso={incident.opened_at} format="age" />)
          </span>
        </Fact>
        <Fact label="Occurrences">
          <span className="data">{incident.occurrence_count}</span>
        </Fact>
        <Fact label="Source">
          <SimTag />
        </Fact>
      </dl>
    </header>
  );
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid min-h-8 grid-cols-[104px_minmax(0,1fr)] items-center gap-2 border-t border-border first:border-t-0">
      <dt className="text-small text-text-muted">{label}</dt>
      <dd className="flex min-w-0 flex-wrap items-center gap-1.5">{children}</dd>
    </div>
  );
}

function Details({ incident }: { incident: IncidentDetail }) {
  return (
    <dl className="px-4 pt-2 pb-3">
      <DetailRow label="Status">
        <IncidentStatusLabel status={incident.status} acknowledgedBy={incident.acknowledged_by} />
      </DetailRow>
      <DetailRow label="Severity">
        <StatusBadge state={incident.severity} />
      </DetailRow>
      <DetailRow label="Peak severity">
        <StatusBadge state={incident.peak_severity} />
      </DetailRow>
      <DetailRow label="Component">
        <Link to={`/components/${incident.component.id}`} className="text-link">
          {incident.component.key}
        </Link>
      </DetailRow>
      <DetailRow label="Failure class">{humanize(incident.failure_class)}</DetailRow>
      <DetailRow label="First seen">
        <Timestamp iso={incident.opened_at} />
      </DetailRow>
      <DetailRow label="Last seen">
        <Timestamp iso={incident.last_seen_at} />
      </DetailRow>
      <DetailRow label="Occurrences">
        <span className="data">{incident.occurrence_count}</span>
      </DetailRow>
      <DetailRow label="Reopened">
        <span className="data">{incident.reopen_count}</span>
      </DetailRow>
      <DetailRow label="Fingerprint">
        <span className="data" translate="no" title={incident.fingerprint}>
          {incident.fingerprint.slice(0, 8)}
        </span>
        <CopyButton value={incident.fingerprint} label="Copy fingerprint" />
      </DetailRow>
      <DetailRow label="Impacted">
        {incident.impacted.length === 0 ? (
          <span className="text-text-muted">none</span>
        ) : (
          incident.impacted.map((impact) => (
            <Link
              key={impact.component.id}
              to={`/components/${impact.component.id}`}
              className="text-link mr-1"
            >
              {impact.component.key}
            </Link>
          ))
        )}
      </DetailRow>
      {incident.resolved_at !== null && (
        <>
          <DetailRow label="Resolved">
            <Timestamp iso={incident.resolved_at} />
          </DetailRow>
          <DetailRow label="Resolution">{humanize(incident.resolution ?? "")}</DetailRow>
        </>
      )}
    </dl>
  );
}

export function IncidentPage() {
  const { incidentId = "" } = useParams();
  const query = useIncident(incidentId);
  const incident = query.data;
  const [active, setActive] = useState<number | null>(null);
  const missing = active !== null && !incident?.evidence.some((item) => item.id === active);
  const selected = useCitedEvidence(incidentId, missing ? active : null);
  const byId = useMemo(
    () =>
      new Map(
        [...(incident?.evidence ?? []), ...(selected.data?.items ?? [])].map((item) => [
          item.id,
          item,
        ]),
      ),
    [incident, selected.data],
  );
  useEffect(() => {
    if (active !== null && byId.has(active)) {
      document.getElementById(`evidence-${String(active)}`)?.scrollIntoView({ block: "nearest" });
    }
  }, [active, byId]);
  const focus: EvidenceFocus = {
    active,
    byId,
    toggle: (id) => {
      setActive((current) => (current === id ? null : id));
    },
  };
  const activeSample = active === null ? null : (byId.get(active)?.sample?.id ?? null);

  if (query.isPending) {
    return (
      <div aria-busy="true">
        <h1 className="sr-only">Incident</h1>
        <SkeletonRows rows={6} />
      </div>
    );
  }
  if (incident === undefined) {
    return (
      <>
        <h1 className="text-display font-semibold">Incident</h1>
        <Card title="Incident" titleId="incident-error-title">
          <LoadError what="this incident" query={query} />
        </Card>
      </>
    );
  }

  return (
    <div className={`flex flex-col gap-4 ${staleClass(query.isError)}`}>
      <Header incident={incident} />
      <div className="grid grid-cols-[minmax(0,1fr)_336px] items-start gap-4 max-xl:grid-cols-1">
        <div className="flex min-w-0 flex-col gap-4">
          <IncidentSignal incident={incident} activeSample={activeSample} />
          {missing && selected.isPending && <p role="status">Loading cited evidence…</p>}
          {missing && selected.isError && <LoadError what="the cited evidence" query={selected} />}
          {missing && selected.data?.items.length === 0 && (
            <p role="status">This citation is not attached to the incident.</p>
          )}
          <EvidenceChain incident={{ ...incident, evidence: [...byId.values()] }} active={active} />
          <DiagnosisPanel incidentId={incident.id} focus={focus} />
        </div>
        <aside className="flex flex-col gap-4 xl:sticky xl:top-4" aria-label="Incident context">
          <Card
            title="Details"
            titleId="details-title"
            meta={<RefreshMeta updatedAt={query.dataUpdatedAt} failed={query.isError} />}
          >
            <Details incident={incident} />
          </Card>
          <Card title="Timeline" titleId="timeline-title" meta={<span>Times shown in UTC</span>}>
            <InvestigationTimeline key={incident.id} incident={incident} />
          </Card>
        </aside>
      </div>
    </div>
  );
}
