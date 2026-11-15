import { Renew, Time, WarningAlt } from "@carbon/icons-react";
import type { ReactNode } from "react";

import { ApiError } from "@/shared/api/client";
import { REFRESH_MS } from "@/shared/api/queries";
import { formatAge, formatUtcTime } from "@/shared/format/time";
import { useNow } from "@/shared/hooks/useNow";

import { Button } from "./Button";
import { CopyButton } from "./CopyButton";

const REFRESH_S = REFRESH_MS / 1000;

export function CorrelationId({ value }: { value: string }) {
  return (
    <p className="flex items-center gap-2 text-small text-text-muted">
      Correlation ID{" "}
      <span className="data text-text" translate="no">
        {value}
      </span>
      <CopyButton value={value} label="Copy correlation ID" />
    </p>
  );
}

/** A refused mutation: what the API said, and that the server audited the attempt. */
export function RefusedAlert({ action, error }: { action: string; error: Error | null }) {
  if (error === null) return null;
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div
      role="alert"
      className="flex flex-col gap-1 border-l-[3px] border-border-strong bg-surface px-3 py-2"
    >
      <p className="font-medium">{action} refused.</p>
      <p className="text-text-muted">
        <ApiErrorSummary error={error} />
        {apiError?.status != null && " The attempt is recorded in the audit log."}
      </p>
      {apiError?.correlationId != null && <CorrelationId value={apiError.correlationId} />}
    </div>
  );
}

/** One sentence on what the API said; shared by load errors and refused actions. */
export function ApiErrorSummary({ error }: { error: Error }) {
  const apiError = error instanceof ApiError ? error : null;
  if (apiError?.status == null) {
    return (
      <>
        The API did not answer; it may be stopped. Start it with{" "}
        <code className="data">make up</code>.
      </>
    );
  }
  return (
    <>
      The API answered {apiError.status} <span className="data">{apiError.code}</span>:{" "}
      {apiError.message}
    </>
  );
}

/** The part of a TanStack query a load error needs. */
export interface FailedQuery {
  error: Error | null;
  errorUpdatedAt: number;
  isFetching: boolean;
  refetch: () => Promise<unknown>;
}

interface LoadErrorProps {
  what: string;
  query: FailedQuery;
  /** What keeps working although this view does not (design system §8). */
  stillWorking?: string;
}

export function LoadError({ what, query, stillWorking }: LoadErrorProps) {
  const { error } = query;
  if (error === null) return null;
  const correlationId = error instanceof ApiError ? error.correlationId : null;
  return (
    <div role="alert" className="flex items-start gap-3 px-4 py-4">
      <WarningAlt size={20} aria-hidden="true" className="mt-0.5 flex-none text-text-muted" />
      <div className="flex flex-col gap-2">
        <p className="font-semibold">Could not load {what}.</p>
        <p className="text-text-muted">
          <ApiErrorSummary error={error} /> Failed at{" "}
          <span className="data">{formatUtcTime(new Date(query.errorUpdatedAt))} UTC</span>.
          {stillWorking !== undefined && <> {stillWorking}</>}
        </p>
        {correlationId !== null && <CorrelationId value={correlationId} />}
        <div>
          <Button
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
            icon={<Renew size={16} aria-hidden="true" />}
          >
            {query.isFetching ? "Retrying…" : "Retry"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-3 px-4 py-4" aria-hidden="true">
      <div className="skeleton h-6 w-40" />
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="skeleton h-5 w-full" />
      ))}
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}

/** What is empty, why, what to do; never styled as a success (§8). */
export function EmptyState({ title, children, action }: EmptyStateProps) {
  return (
    <div className="flex max-w-[72ch] flex-col gap-1 px-4 py-4">
      <p className="font-medium">{title}</p>
      <div className="text-text-muted">{children}</div>
      {action !== undefined && <div className="mt-2">{action}</div>}
    </div>
  );
}

interface RefreshMetaProps {
  updatedAt: number;
  failed: boolean;
}

/** "Updated 4 s ago", or the stale-view notice once a refresh failed with data on screen. */
export function RefreshMeta({ updatedAt, failed }: RefreshMetaProps) {
  const now = useNow();
  if (updatedAt === 0) return null;
  const at = new Date(updatedAt);
  if (failed) {
    return (
      <span className="flex items-center gap-1.5">
        <Time size={16} aria-hidden="true" />
        Data from <span className="data">{formatUtcTime(at)} UTC</span>, {formatAge(at, now)};
        refresh failed, retrying every {REFRESH_S}&nbsp;s.
      </span>
    );
  }
  return (
    <span title={`Refreshes every ${String(REFRESH_S)} s`}>
      Updated <span className="data">{formatAge(at, now)}</span>
    </span>
  );
}
