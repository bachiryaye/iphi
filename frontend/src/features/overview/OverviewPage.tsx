import { Link } from "react-router";

import { ComponentsTable } from "@/features/components/ComponentsTable";
import { IncidentList } from "@/features/incidents/IncidentList";
import { useActiveIncidents, useComponents, usePlatforms } from "@/shared/api/queries";
import { SimTag } from "@/shared/status/SimTag";
import { Card } from "@/shared/ui/Card";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

import { PlatformHealthCard } from "./PlatformHealthCard";
import { ReadinessPanel } from "./ReadinessPanel";

const DETECTION_GOES_ON = "Detection continues on the server; only this view is not updating.";

function PlatformHealthSection() {
  const platforms = usePlatforms();
  const components = useComponents();
  const platform = platforms.data?.items[0];
  const critical = platform?.health.state === "critical";
  return (
    <Card
      title="Platform health"
      titleId="platform-health-title"
      busy={platforms.isPending}
      critical={critical && !platforms.isError}
      meta={<RefreshMeta updatedAt={platforms.dataUpdatedAt} failed={platforms.isError} />}
    >
      {platforms.isPending && <SkeletonRows rows={3} />}
      {platforms.isError && platforms.data === undefined && (
        <LoadError what="platform health" query={platforms} stillWorking={DETECTION_GOES_ON} />
      )}
      {platforms.data !== undefined && platform === undefined && (
        <EmptyState title="No platform configured.">
          The database holds no platform. Seed the simulated platform with{" "}
          <code className="data">make up</code>, which runs the bootstrap.
        </EmptyState>
      )}
      {platform !== undefined && (
        <div className={staleClass(platforms.isError)}>
          <PlatformHealthCard platform={platform} components={components.data?.items ?? []} />
        </div>
      )}
    </Card>
  );
}

function ActiveIncidentsSection() {
  const incidents = useActiveIncidents();
  const items = incidents.data?.items;
  const count =
    incidents.data === undefined
      ? ""
      : ` (${String(incidents.data.items.length)}${incidents.data.more ? "+" : ""})`;
  return (
    <Card
      title={`Active incidents${count}`}
      titleId="active-incidents-title"
      busy={incidents.isPending}
      meta={
        <>
          <SimTag />
          <Link to="/incidents" className="text-link">
            All incidents
          </Link>
        </>
      }
      className="flex flex-col"
    >
      {incidents.isPending && <SkeletonRows rows={2} />}
      {incidents.isError && incidents.data === undefined && (
        <LoadError what="incidents" query={incidents} stillWorking={DETECTION_GOES_ON} />
      )}
      {items?.length === 0 && (
        <EmptyState
          title="No active incidents."
          action={
            <Link to="/scenarios" className="text-link">
              Open scenarios
            </Link>
          }
        >
          Every component is evaluated every 5 s; an incident opens when a rule stays in Warning or
          Critical past its debounce. Start a fault scenario to see one.
        </EmptyState>
      )}
      {items !== undefined && items.length > 0 && (
        <div className={staleClass(incidents.isError)}>
          <IncidentList incidents={items.slice(0, 5)} />
          {items.length > 5 && (
            <p className="border-t border-border px-4 py-2.5 text-small text-text-muted">
              {items.length - 5}
              {incidents.data?.more === true ? "+" : ""} more in{" "}
              <Link to="/incidents" className="text-link">
                Incidents
              </Link>
              .
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function MeterLegend() {
  return (
    <span className="flex items-center gap-3 max-lg:hidden">
      <span className="inline-flex items-center gap-1.5">
        <span aria-hidden="true" className="h-1.5 w-4.5 rounded-[3px] bg-meter-normal" />
        normal range
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span aria-hidden="true" className="size-2 rounded-full bg-text" />
        current value
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span aria-hidden="true" className="h-3 w-2 border-x border-text-muted" />
        warning, critical thresholds
      </span>
    </span>
  );
}

function ComponentsSection() {
  const components = useComponents();
  return (
    <Card
      title="Components"
      titleId="components-title"
      busy={components.isPending}
      meta={
        <>
          <MeterLegend />
          <SimTag />
          <RefreshMeta updatedAt={components.dataUpdatedAt} failed={components.isError} />
        </>
      }
    >
      {components.isPending && <SkeletonRows rows={7} />}
      {components.isError && components.data === undefined && (
        <LoadError what="components" query={components} stillWorking={DETECTION_GOES_ON} />
      )}
      {components.data?.items.length === 0 && (
        <EmptyState title="No components.">
          The platform has no component yet; the bootstrap seeds the seven simulated ones.
        </EmptyState>
      )}
      {components.data !== undefined && components.data.items.length > 0 && (
        <div className={staleClass(components.isError)}>
          <ComponentsTable components={components.data.items} />
        </div>
      )}
    </Card>
  );
}

export function OverviewPage() {
  return (
    <>
      <h1 className="text-display font-semibold">Overview</h1>
      <div className="grid grid-cols-[minmax(0,5fr)_minmax(0,7fr)] gap-4 max-xl:grid-cols-1">
        <PlatformHealthSection />
        <ActiveIncidentsSection />
      </div>
      <ComponentsSection />
      <ReadinessPanel />
    </>
  );
}
