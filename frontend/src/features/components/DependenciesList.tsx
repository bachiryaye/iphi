import { useT } from "@/shared/i18n/context";
import { Link } from "react-router";

import type { Component, ComponentDetail, ComponentRef } from "@/shared/api/types";
import { humanize } from "@/shared/format/labels";
import { HealthBadge } from "@/shared/status/HealthBadge";

function Row({
  refs,
  all,
  note,
}: {
  refs: ComponentRef;
  all: Map<string, Component>;
  note: string;
}) {
  const component = all.get(refs.id);
  return (
    <li className="flex items-center justify-between gap-3 py-1.5">
      <span className="flex min-w-0 items-center gap-2">
        {component !== undefined && <HealthBadge health={component.health} />}
        <Link
          to={`/components/${refs.id}`}
          className="truncate font-medium text-text hover:underline"
        >
          {refs.key}
        </Link>
      </span>
      <span className="text-small whitespace-nowrap text-text-muted">{note}</span>
    </li>
  );
}

function Side({
  title,
  deps,
  all,
  empty,
}: {
  title: string;
  deps: ComponentDetail["upstream"];
  all: Map<string, Component>;
  empty: string;
}) {
  const t = useT();
  return (
    <section aria-label={title}>
      <h3 className="text-small font-medium text-text-muted">{title}</h3>
      {deps.length === 0 ? (
        <p className="py-1.5 text-text-muted">{empty}</p>
      ) : (
        <ul>
          {deps.map((d) => (
            <Row key={d.component.id} refs={d.component} all={all} note={humanize(d.kind, t)} />
          ))}
        </ul>
      )}
    </section>
  );
}

/** Upstream, the component, then its direct dependents (§6.3), with their current states. */
export function DependenciesList({
  detail,
  components,
}: {
  detail: ComponentDetail;
  components: readonly Component[];
}) {
  const t = useT();
  const all = new Map(components.map((c) => [c.id, c]));
  return (
    <div className="flex flex-col gap-3 px-4 py-3">
      <Side
        title={t("Upstream")}
        deps={detail.upstream}
        all={all}
        empty={t("None: {key} is a source.", { key: detail.key })}
      />
      <p className="flex items-center gap-2 border-y border-border py-2">
        <HealthBadge health={detail.health} />
        <span className="font-semibold">{detail.key}</span>
        <span className="ml-auto text-small text-text-muted">{t("this component")}</span>
      </p>
      <Side
        title={t("Downstream")}
        deps={detail.downstream}
        all={all}
        empty={t("None: nothing consumes {key}.", { key: detail.key })}
      />
    </div>
  );
}
