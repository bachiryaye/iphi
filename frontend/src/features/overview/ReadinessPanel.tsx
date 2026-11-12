import { Copy, Renew, Time, WarningAlt } from "@carbon/icons-react";
import { useState } from "react";

import { ApiError } from "@/shared/api/client";
import {
  type CheckName,
  type Readiness,
  type ReadinessCheck,
  READINESS_REFRESH_MS,
  useReadiness,
} from "@/shared/api/readiness";
import { formatUtcDateTime, formatUtcTime } from "@/shared/format/time";
import { StatusBadge } from "@/shared/status/StatusBadge";
import { Card } from "@/shared/ui/Card";

const CHECK_LABEL: Record<CheckName, string> = {
  database: "Database",
  migrations: "Schema migrations",
  worker: "Worker heartbeat",
  ai_provider: "AI diagnosis provider",
};

const REFRESH_S = READINESS_REFRESH_MS / 1000;

function CheckStatusCell({ status }: { status: ReadinessCheck["status"] }) {
  if (status === "ok") return <StatusBadge state="healthy" label="OK" />;
  if (status === "failed") return <StatusBadge state="critical" label="Failed" />;
  return (
    <span className="inline-flex items-center gap-1.5 text-text-muted">
      <span aria-hidden="true" className="w-3.5" />
      Off
    </span>
  );
}

function Verdict({ readiness }: { readiness: Readiness }) {
  const ready = readiness.status === "ready";
  const failed = readiness.checks.filter((check) => check.status === "failed").length;
  return (
    <div className="flex items-center gap-2 px-4 py-4">
      <StatusBadge
        state={ready ? "healthy" : "critical"}
        label={ready ? "API ready" : "API not ready"}
        size="lg"
      />
      {!ready && (
        <p className="text-text-muted">
          {failed === 1 ? "1 check failed." : `${String(failed)} checks failed.`}
        </p>
      )}
    </div>
  );
}

function EvidenceTime({ iso }: { iso: string }) {
  const at = new Date(iso);
  return (
    <time dateTime={iso} className="data" title={formatUtcDateTime(at)}>
      {formatUtcTime(at)} UTC
    </time>
  );
}

function ChecksTable({ checks }: { checks: readonly ReadinessCheck[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="text-left text-small text-text-muted">
            <th scope="col" className="border-y border-border py-2 pr-3 pl-4 font-medium">
              Check
            </th>
            <th scope="col" className="border-y border-border px-3 py-2 font-medium">
              Status
            </th>
            <th scope="col" className="border-y border-border px-3 py-2 font-medium">
              Detail
            </th>
            <th scope="col" className="border-y border-border py-2 pr-4 pl-3 font-medium">
              Evidence time
            </th>
          </tr>
        </thead>
        <tbody>
          {checks.map((check) => (
            <tr
              key={check.name}
              className={
                check.status === "failed"
                  ? "[&>*:first-child]:shadow-[inset_3px_0_0_var(--status-critical)]"
                  : undefined
              }
            >
              <th
                scope="row"
                className="h-11 border-b border-border py-0 pr-3 pl-4 text-left font-medium whitespace-nowrap"
              >
                {CHECK_LABEL[check.name]}
              </th>
              <td className="border-b border-border px-3 whitespace-nowrap">
                <CheckStatusCell status={check.status} />
              </td>
              <td className="border-b border-border px-3">{check.detail}</td>
              <td className="border-b border-border pr-4 pl-3 whitespace-nowrap">
                {check.observed_at ? (
                  <EvidenceTime iso={check.observed_at} />
                ) : (
                  <span className="text-text-muted">
                    <span aria-hidden="true">—</span>
                    <span className="sr-only">No evidence time</span>
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="flex flex-col gap-3 px-4 py-4" aria-hidden="true">
      <div className="skeleton h-6 w-40" />
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="skeleton h-5 w-full" />
      ))}
    </div>
  );
}

const COPIED_FEEDBACK_MS = 2000;

function CorrelationId({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => {
      setCopied(false);
    }, COPIED_FEEDBACK_MS);
  };
  return (
    <p className="flex items-center gap-2 text-small text-text-muted">
      Correlation ID{" "}
      <span className="data text-text" translate="no">
        {value}
      </span>
      <button
        type="button"
        aria-label="Copy correlation ID"
        onClick={() => void copy()}
        className="inline-grid size-6 cursor-pointer place-items-center rounded-control text-text-muted hover:bg-surface-sunken hover:text-text"
      >
        <Copy size={16} aria-hidden="true" />
      </button>
      <span aria-live="polite">{copied ? "Copied" : ""}</span>
    </p>
  );
}

interface LoadErrorProps {
  error: Error;
  failedAt: number;
  retrying: boolean;
  onRetry: () => void;
}

function LoadError({ error, failedAt, retrying, onRetry }: LoadErrorProps) {
  const apiError = error instanceof ApiError ? error : null;
  const correlationId = apiError?.correlationId ?? null;

  return (
    <div role="alert" className="flex items-start gap-3 px-4 py-4">
      <WarningAlt size={20} aria-hidden="true" className="mt-0.5 flex-none text-text-muted" />
      <div className="flex flex-col gap-2">
        <p className="font-semibold">Could not load monitor readiness.</p>
        <p className="text-text-muted">
          {apiError?.status != null ? (
            <>
              The API answered {apiError.status} <span className="data">{apiError.code}</span>.
            </>
          ) : (
            <>
              The API did not answer; it may be stopped. Start it with{" "}
              <code className="data">make up</code>.
            </>
          )}{" "}
          Failed at <span className="data">{formatUtcTime(new Date(failedAt))} UTC</span>.
        </p>
        {correlationId !== null && <CorrelationId value={correlationId} />}
        <div>
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying}
            className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-control border border-border-strong bg-surface px-3 font-medium hover:bg-surface-sunken disabled:cursor-default disabled:text-text-muted"
          >
            <Renew size={16} aria-hidden="true" />
            {retrying ? "Retrying…" : "Retry"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ReadinessPanel() {
  const { data, error, isPending, isError, isFetching, refetch, dataUpdatedAt, errorUpdatedAt } =
    useReadiness();
  const stale = isError && data !== undefined;
  const retry = () => void refetch();

  const meta =
    data === undefined ? undefined : stale ? (
      <span className="flex items-center gap-1.5">
        <Time size={16} aria-hidden="true" />
        Data from <span className="data">{formatUtcTime(new Date(dataUpdatedAt))} UTC</span>;
        refresh failed, retrying every {REFRESH_S}&nbsp;s.
      </span>
    ) : (
      <span>
        Checked <span className="data">{formatUtcTime(new Date(data.checked_at))} UTC</span>,
        refreshes every {REFRESH_S}&nbsp;s
      </span>
    );

  return (
    <Card title="Monitor readiness" titleId="readiness-title" meta={meta} busy={isPending}>
      {isPending && <LoadingRows />}
      {isError && data === undefined && (
        <LoadError error={error} failedAt={errorUpdatedAt} retrying={isFetching} onRetry={retry} />
      )}
      {data !== undefined && (
        <div className={stale ? "text-text-muted" : undefined}>
          <Verdict readiness={data} />
          <ChecksTable checks={data.checks} />
        </div>
      )}
    </Card>
  );
}
