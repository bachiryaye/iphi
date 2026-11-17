import { useDiagnostics } from "@/shared/api/queries";
import type { Diagnostic } from "@/shared/api/types";
import { Timestamp } from "@/shared/status/Timestamp";
import { Card } from "@/shared/ui/Card";
import { EmptyState, LoadError, RefreshMeta, SkeletonRows } from "@/shared/ui/QueryStates";
import { staleClass } from "@/shared/ui/stale";

import { DiagnosisBody, type EvidenceFocus } from "./DiagnosisCard";

function Deterministic({ diagnostic, focus }: { diagnostic: Diagnostic; focus: EvidenceFocus }) {
  return (
    <Card
      title="Diagnosis: deterministic"
      titleId="deterministic-diagnosis-title"
      meta={
        <span>
          Generated <Timestamp iso={diagnostic.created_at} />
        </span>
      }
    >
      <DiagnosisBody diagnostic={diagnostic} focus={focus} />
    </Card>
  );
}

export function DiagnosisPanel({
  incidentId,
  focus,
}: {
  incidentId: string;
  focus: EvidenceFocus;
}) {
  const query = useDiagnostics(incidentId);
  const latest = query.data?.items[0];
  const comparison = query.data?.items.find((item) => item.id === latest?.deterministic_id);
  const failed = latest !== undefined && latest.status !== "succeeded";
  return (
    <div className={`flex flex-col gap-4 ${staleClass(query.isError && query.data !== undefined)}`}>
      <Card
        title={
          latest === undefined
            ? "Diagnosis"
            : latest.kind === "llm"
              ? "Diagnosis: AI"
              : "Diagnosis: deterministic"
        }
        titleId="diagnosis-title"
        busy={query.isPending}
        meta={
          <>
            <RefreshMeta updatedAt={query.dataUpdatedAt} failed={query.isError} />
            {latest?.kind === "deterministic" && (
              <span>
                Generated <Timestamp iso={latest.created_at} /> by {latest.created_by}
              </span>
            )}
          </>
        }
      >
        {query.isPending && <SkeletonRows rows={4} />}
        {query.isError && query.data === undefined && (
          <LoadError what="the diagnosis" query={query} />
        )}
        {query.data !== undefined && latest === undefined && (
          <EmptyState title="No diagnosis yet.">
            Diagnose builds a deterministic reading of the stored evidence: facts, hypotheses with
            their uncertainty, checks to run. It needs no AI provider.
          </EmptyState>
        )}
        {latest !== undefined && (
          <>
            {latest.kind === "llm" && (
              <div className="border-b border-border px-4 py-3 text-small text-text-muted">
                <p className="font-medium text-text">AI-generated — verify against evidence</p>
                <p className="data break-words">
                  {latest.model}
                  {latest.provider === "fake" && " · Local test provider; no language model called"}
                </p>
                <p>
                  Generated <Timestamp iso={latest.created_at} /> · {latest.status}
                </p>
                <p>Citations confirm references; they do not prove that a claim is true.</p>
              </div>
            )}
            {failed && (
              <p
                role="status"
                className="border-l-[3px] border-border-strong bg-surface-sunken px-4 py-3"
              >
                AI diagnosis unavailable or rejected ({latest.error_code ?? latest.status}).
                Monitoring continues. The deterministic diagnosis is shown below.
              </p>
            )}
            <DiagnosisBody diagnostic={latest} focus={focus} />
          </>
        )}
      </Card>
      {comparison !== undefined &&
        (failed ? (
          <Deterministic diagnostic={comparison} focus={focus} />
        ) : (
          <details className="rounded-card border border-border bg-surface">
            <summary className="cursor-pointer px-4 py-3 font-medium">
              Compare with deterministic diagnosis
            </summary>
            <Deterministic diagnostic={comparison} focus={focus} />
          </details>
        ))}
      {latest?.kind === "llm" && comparison === undefined && (
        <p className="text-text-muted">
          The deterministic comparison could not be loaded. Use Diagnose to generate a deterministic
          reading.
        </p>
      )}
    </div>
  );
}
