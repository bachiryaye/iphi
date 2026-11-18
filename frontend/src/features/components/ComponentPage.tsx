import { ChevronRight } from "@carbon/icons-react";
import { Link, useParams } from "react-router";

import { useComponent, useComponentRules, useComponents, useIncidents } from "@/shared/api/queries";
import type { ComponentDetail, Incident } from "@/shared/api/types";
import { HealthBadge } from "@/shared/status/HealthBadge";
import { ImpactNote } from "@/shared/status/ImpactNote";
import { SimTag } from "@/shared/status/SimTag";
import { Timestamp } from "@/shared/status/Timestamp";
import { Card } from "@/shared/ui/Card";
import { LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

import { IncidentList } from "@/features/incidents/IncidentList";

import { DependenciesList } from "./DependenciesList";
import { LogsCard } from "./LogsCard";
import { MetricPanel } from "./MetricPanel";
import { RulesTable } from "./RulesTable";

function Header({
  detail,
  openIncident,
}: {
  detail: ComponentDetail;
  openIncident: Incident | undefined;
}) {
  const reason = detail.reason;
  return (
    <header className="flex flex-col gap-2">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-small text-text-muted">
        <Link to="/components" className="text-link">
          Components
        </Link>
        <ChevronRight size={16} aria-hidden="true" />
        <span className="data text-text">{detail.key}</span>
      </nav>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <HealthBadge health={detail.health} size="lg" />
        <h1 className="text-display font-semibold">{detail.key}</h1>
        {detail.health.since !== null && (
          <span className="text-text-muted">
            since <Timestamp iso={detail.health.since} />
          </span>
        )}
        {openIncident !== undefined && (
          <Link
            to={`/incidents/${openIncident.id}`}
            className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-control border border-accent bg-accent px-3 font-medium text-surface hover:brightness-95"
          >
            Open incident {openIncident.reference}
          </Link>
        )}
      </div>
      <dl className="flex flex-wrap items-center gap-y-1 text-small [&>div]:flex [&>div]:items-center [&>div]:gap-2 [&>div]:border-l [&>div]:border-border [&>div]:px-4 [&>div:first-child]:border-l-0 [&>div:first-child]:pl-0">
        <div>
          <dt className="text-text-muted">Type</dt>
          <dd>{detail.type}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Criticality</dt>
          <dd>{detail.criticality}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Reason</dt>
          <dd>
            {reason === null ? (
              detail.health.state === "healthy" ? (
                "every rule Healthy"
              ) : (
                (detail.health.stale_reason ?? "No stored evaluation explains this state yet.")
              )
            ) : (
              <>
                <span className="data">
                  {reason.rule.key} v{reason.rule.version}
                </span>{" "}
                {reason.explanation}
              </>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">Last evaluation</dt>
          <dd>
            {detail.health.evaluated_at === null ? (
              "never"
            ) : (
              <Timestamp iso={detail.health.evaluated_at} />
            )}
          </dd>
        </div>
        <div>
          <dt className="sr-only">Source</dt>
          <dd>
            <SimTag />
          </dd>
        </div>
      </dl>
      <ImpactNote by={detail.impacted_by} />
      {detail.health.stale && (
        <p className="text-small text-text-muted">{detail.health.stale_reason}</p>
      )}
    </header>
  );
}

export function ComponentPage() {
  const { componentId = "" } = useParams();
  const component = useComponent(componentId);
  const rules = useComponentRules(componentId);
  const all = useComponents();
  const incidents = useIncidents({ component_id: componentId, limit: 10 });
  const detail = component.data;
  const openIncident = incidents.data?.items.find((i) => i.status !== "resolved");

  if (component.isPending) {
    return (
      <div aria-busy="true">
        <h1 className="sr-only">Component</h1>
        <SkeletonRows rows={6} />
      </div>
    );
  }
  if (detail === undefined) {
    return (
      <>
        <h1 className="text-display font-semibold">Component</h1>
        <Card title="Component" titleId="component-error-title">
          <LoadError what="this component" query={component} />
        </Card>
      </>
    );
  }

  return (
    <div className={`flex flex-col gap-4 ${staleClass(component.isError)}`}>
      <Header detail={detail} openIncident={openIncident} />
      <div className="grid grid-cols-[minmax(0,1fr)_336px] items-start gap-4 max-xl:grid-cols-1">
        <div className="flex min-w-0 flex-col gap-4">
          <MetricPanel detail={detail} rules={rules.data?.rules ?? []} />
          <Card
            title="Rules"
            titleId="rules-title"
            busy={rules.isPending}
            meta={<RefreshMeta updatedAt={rules.dataUpdatedAt} failed={rules.isError} />}
          >
            {rules.isPending && <SkeletonRows rows={4} />}
            {rules.isError && rules.data === undefined && (
              <LoadError what="rule evaluations" query={rules} />
            )}
            {rules.data !== undefined && (
              <div className={staleClass(rules.isError)}>
                <RulesTable rules={rules.data.rules} />
              </div>
            )}
          </Card>
          <LogsCard componentId={detail.id} />
        </div>
        <aside className="flex flex-col gap-4 xl:sticky xl:top-4" aria-label="Context">
          <Card title="Dependencies" titleId="dependencies-title" meta={<span>data flow</span>}>
            <DependenciesList detail={detail} components={all.data?.items ?? []} />
          </Card>
          <Card title="Incidents" titleId="component-incidents-title" meta={<span>latest 10</span>}>
            {incidents.isPending && <SkeletonRows rows={2} />}
            {incidents.isError && incidents.data === undefined && (
              <LoadError what="incidents" query={incidents} />
            )}
            {incidents.data?.items.length === 0 && (
              <p className="px-4 py-3 text-text-muted">No incident recorded on {detail.key}.</p>
            )}
            {incidents.data !== undefined && incidents.data.items.length > 0 && (
              <IncidentList incidents={incidents.data.items} compact />
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
}
