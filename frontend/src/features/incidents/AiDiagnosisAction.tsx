import { useDiagnose, useMutationGuard, useSystemStatus } from "@/shared/api/queries";
import { Button } from "@/shared/ui/Button";
import { RefusedAlert } from "@/shared/ui/QueryStates";

export function AiDiagnosisAction({ incidentId }: { incidentId: string }) {
  const { allowed } = useMutationGuard();
  const status = useSystemStatus().data?.ai_provider;
  const diagnosis = useDiagnose(incidentId, "llm");
  const disabled = status === undefined || status.status === "disabled";
  return (
    <div className="flex flex-col items-end gap-1 max-xl:items-start">
      <Button
        disabled={!allowed || disabled || diagnosis.isPending}
        onClick={() => {
          diagnosis.mutate(globalThis.crypto.randomUUID());
        }}
      >
        {diagnosis.isPending ? "Requesting AI diagnosis…" : "AI diagnosis"}
      </Button>
      {disabled && (
        <p className="text-small text-text-muted">
          AI diagnosis off. Deterministic diagnosis remains available.
        </p>
      )}
      <RefusedAlert action="AI diagnosis" error={diagnosis.error} />
    </div>
  );
}
