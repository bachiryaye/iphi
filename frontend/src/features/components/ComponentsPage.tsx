import { useT } from "@/shared/i18n/context";
import { useComponents } from "@/shared/api/queries";
import type { ComponentType, HealthState } from "@/shared/api/types";
import { useSearchFilter } from "@/shared/hooks/useSearchFilter";
import { SimTag } from "@/shared/status/SimTag";
import { Card } from "@/shared/ui/Card";
import { FilterSelect } from "@/shared/ui/FilterSelect";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

import { ComponentsTable } from "./ComponentsTable";

const STATES: readonly HealthState[] = ["critical", "warning", "unknown", "healthy"];
const TYPES: readonly ComponentType[] = [
  "source", "gateway", "collector", "historian", "database", "api", "analytics",
]; // prettier-ignore

export function ComponentsPage() {
  const t = useT();
  const components = useComponents();
  const [state, setState] = useSearchFilter("state", STATES);
  const [type, setType] = useSearchFilter("type", TYPES);
  const items = (components.data?.items ?? []).filter(
    (c) => (state === "" || c.health.state === state) && (type === "" || c.type === type),
  );
  return (
    <>
      <h1 className="text-display font-semibold">{t("Components")}</h1>
      <div className="flex flex-wrap items-center gap-4">
        <FilterSelect label={t("State")} value={state} options={STATES} onChange={setState} />
        <FilterSelect label={t("Type")} value={type} options={TYPES} onChange={setType} />
      </div>
      <Card
        title={t("Components")}
        titleId="components-list-title"
        busy={components.isPending}
        meta={
          <>
            <SimTag />
            <RefreshMeta updatedAt={components.dataUpdatedAt} failed={components.isError} />
          </>
        }
      >
        {components.isPending && <SkeletonRows rows={7} />}
        {components.isError && components.data === undefined && (
          <LoadError what={t("components")} query={components} />
        )}
        {components.data !== undefined && items.length === 0 && (
          <EmptyState title={t("No component matches these filters.")}>
            {components.data.items.length} {t("components exist; clear a filter to see them.")}
          </EmptyState>
        )}
        {items.length > 0 && (
          <div className={staleClass(components.isError)}>
            <ComponentsTable components={items} />
          </div>
        )}
      </Card>
    </>
  );
}
