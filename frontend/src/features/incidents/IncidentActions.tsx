import { useT } from "@/shared/i18n/context";
import { Checkmark, DocumentView, UserFollow } from "@carbon/icons-react";
import { useId, useState } from "react";

import { useAcknowledge, useDiagnose, useMutationGuard, useResolve } from "@/shared/api/queries";
import type { IncidentDetail } from "@/shared/api/types";
import { Button } from "@/shared/ui/Button";
import { RefusedAlert } from "@/shared/ui/QueryStates";
import { AiDiagnosisAction } from "./AiDiagnosisAction";
import { ReportActions } from "./ReportActions";

function newKey(): string {
  return globalThis.crypto.randomUUID();
}

/** Acknowledge, resolve and diagnose; disabled with the reason when the API refuses them. */
export function IncidentActions({ incident }: { incident: IncidentDetail }) {
  const t = useT();
  const { allowed, reason } = useMutationGuard();
  const acknowledge = useAcknowledge(incident.id);
  const resolve = useResolve(incident.id);
  const diagnose = useDiagnose(incident.id);
  const [resolving, setResolving] = useState(false);
  const [comment, setComment] = useState("");
  const commentId = useId();

  const resolved = incident.status === "resolved";
  const failure =
    (acknowledge.error && { action: t("Acknowledge"), error: acknowledge.error }) ||
    (resolve.error && { action: t("Resolve"), error: resolve.error }) ||
    (diagnose.error && { action: t("Diagnose"), error: diagnose.error }) ||
    null;

  const submit = (event: { preventDefault: () => void }) => {
    event.preventDefault();
    resolve.mutate(comment.trim(), {
      onSuccess: () => {
        setResolving(false);
        setComment("");
      },
    });
  };

  return (
    <div className="flex flex-col items-end gap-2 max-xl:items-start">
      <div className="flex flex-wrap gap-2">
        <Button
          icon={<UserFollow size={16} aria-hidden="true" />}
          disabled={!allowed || incident.status !== "open" || acknowledge.isPending}
          onClick={() => {
            acknowledge.mutate();
          }}
        >
          {incident.status === "acknowledged" ? t("Acknowledged") : t("Acknowledge")}
        </Button>
        <Button
          icon={<Checkmark size={16} aria-hidden="true" />}
          disabled={!allowed || resolved || !incident.resolvable}
          aria-expanded={resolving}
          onClick={() => {
            setResolving((v) => !v);
          }}
          title={
            !resolved && !incident.resolvable
              ? t("The condition is still active; the incident resolves itself once it clears.")
              : undefined
          }
        >
          {t("Resolve…")}
        </Button>
        <Button
          variant="primary"
          icon={<DocumentView size={16} aria-hidden="true" />}
          disabled={!allowed || diagnose.isPending}
          onClick={() => {
            diagnose.mutate(newKey());
          }}
        >
          {diagnose.isPending ? t("Diagnosing…") : t("Diagnose")}
        </Button>
      </div>
      <AiDiagnosisAction incidentId={incident.id} />
      <ReportActions incidentId={incident.id} reference={incident.reference} />
      {reason !== undefined && !allowed && (
        <p className="max-w-[60ch] text-right text-small text-text-muted max-xl:text-left">
          {t("Incident changes are disabled:")} {t.label(reason)} {t("Reports remain available.")}
        </p>
      )}
      {allowed && !resolved && !incident.resolvable && (
        <p className="max-w-[60ch] text-right text-small text-text-muted max-xl:text-left">
          {t(
            "Resolve is unavailable while the condition is active; the incident resolves itself once the rule clears.",
          )}
        </p>
      )}
      {resolving && (
        <form
          onSubmit={submit}
          className="flex w-full max-w-md flex-col gap-2 rounded-card border border-border bg-surface p-3"
        >
          <label htmlFor={commentId} className="font-medium">
            {t("Why is this incident closed?")}
          </label>
          <textarea
            id={commentId}
            name="resolution-comment"
            autoComplete="off"
            required
            maxLength={4000}
            rows={3}
            value={comment}
            onChange={(event) => {
              setComment(event.target.value);
            }}
            className="rounded-control border border-border-strong bg-surface px-2 py-1.5 text-text"
          />
          <p className="text-small text-text-muted">{t("Kept in the incident timeline.")}</p>
          <div className="flex gap-2">
            <Button
              type="submit"
              variant="primary"
              disabled={comment.trim() === "" || resolve.isPending}
            >
              {resolve.isPending ? t("Resolving…") : t("Resolve incident")}
            </Button>
            <Button
              onClick={() => {
                setResolving(false);
              }}
            >
              {t("Cancel")}
            </Button>
          </div>
        </form>
      )}
      {failure !== null && <RefusedAlert action={failure.action} error={failure.error} />}
    </div>
  );
}
