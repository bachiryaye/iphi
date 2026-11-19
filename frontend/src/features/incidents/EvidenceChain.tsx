import { useT } from "@/shared/i18n/context";
import { useState } from "react";

import type { IncidentDetail, IncidentEvidence } from "@/shared/api/types";
import { SimTag } from "@/shared/status/SimTag";
import { Timestamp } from "@/shared/status/Timestamp";
import { Button } from "@/shared/ui/Button";
import { Card } from "@/shared/ui/Card";

import { evidenceSummary, evidenceTime } from "./evidenceText";

interface EvidenceChainProps {
  incident: IncidentDetail;
  active: number | null;
}

/** Immutable evidence of the incident, each row reachable from its chip (P3). */
/** Samples cited by supporting evaluations repeat a whole window; they stay one click away. */
function isKey(item: IncidentEvidence): boolean {
  return item.sample === null || item.role !== "supporting";
}

export function EvidenceChain({ incident, active }: EvidenceChainProps) {
  const t = useT();
  const [showAll, setShowAll] = useState(false);
  const all = incident.evidence;
  const items = showAll ? all : all.filter((item) => isKey(item) || item.id === active);
  const hidden = all.length - items.length;
  const trigger = items.find((e) => e.role === "trigger" && e.evaluation !== null)?.evaluation;
  return (
    <Card
      title={t("Evidence chain")}
      titleId="evidence-title"
      meta={
        <span>
          {incident.evidence_count} {incident.evidence_count === 1 ? "item" : "items"}
          {t(", immutable")}
        </span>
      }
    >
      {trigger != null && (
        <p className="flex flex-wrap items-center gap-x-2 border-b border-border px-4 py-2.5 text-small">
          <span className="text-text-muted">{t("Rule")}</span>
          <span className="data">
            {trigger.rule.key} v{trigger.rule.version}
          </span>
          <span aria-hidden="true" className="text-text-muted">
            ›
          </span>
          <span className="text-text-muted">{t("Evaluation")}</span>
          <span className="data">#{trigger.id}</span>
          <span aria-hidden="true" className="text-text-muted">
            ›
          </span>
          <span className="text-text-muted">
            {trigger.evidence.sample_ids.length} {t("samples,")} {trigger.evidence.log_ids.length}{" "}
            {t("logs")}
          </span>
        </p>
      )}
      {all.length === 0 ? (
        <p className="px-4 py-3 text-text-muted">{t("No evidence stored for this incident.")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">{t("Kind")}</th>
                <th scope="col">{t("Observation")}</th>
                <th scope="col">{t("Component")}</th>
                <th scope="col">{t("Time (UTC)")}</th>
                <th scope="col">{t("Role")}</th>
                <th scope="col">
                  <span className="sr-only">{t("Source")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  id={`evidence-${String(item.id)}`}
                  className={active === item.id ? "row-highlight" : undefined}
                >
                  <th scope="row" className="data font-medium">
                    {item.label}
                  </th>
                  <td className="text-text-muted">{item.kind}</td>
                  <td className="py-2">{evidenceSummary(item)}</td>
                  <td className="whitespace-nowrap">{item.component?.key ?? "—"}</td>
                  <td className="whitespace-nowrap">
                    <Timestamp iso={evidenceTime(item)} suffix={false} />
                  </td>
                  <td className="text-text-muted">{item.role}</td>
                  <td>
                    <SimTag />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(hidden > 0 || showAll) && (
        <div className="flex items-center gap-3 border-t border-border px-4 py-2.5 text-small text-text-muted">
          {showAll
            ? t("Showing every item.")
            : t("{count} samples cited by supporting evaluations are hidden.", { count: hidden })}
          <Button
            variant="quiet"
            className="h-7"
            aria-expanded={showAll}
            onClick={() => {
              setShowAll((v) => !v);
            }}
          >
            {showAll
              ? t("Show key items only")
              : t("Show all {count} items", { count: all.length })}
          </Button>
        </div>
      )}
      {incident.evidence_next_cursor !== null && (
        <p className="border-t border-border px-4 py-2.5 text-small text-text-muted">
          {t("Loaded")} {all.length} {t("of")} {incident.evidence_count}{" "}
          {t("items. Choose a citation to load its evidence.")}
        </p>
      )}
    </Card>
  );
}
