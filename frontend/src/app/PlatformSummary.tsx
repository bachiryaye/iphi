import { Link } from "react-router";

import { usePlatforms } from "@/shared/api/queries";
import { StatusBadge } from "@/shared/status/StatusBadge";

/** The top bar always carries the platform state (§5), muted when it could not refresh. */
export function PlatformSummary() {
  const { data, isError, isPending } = usePlatforms();
  const platform = data?.items[0];

  if (isPending) return <p className="min-w-0 truncate text-text-muted">Loading platform…</p>;
  if (platform === undefined) {
    return (
      <p className="min-w-0 truncate text-text-muted">
        {isError ? "Platform state unavailable" : "No platform configured"}
      </p>
    );
  }
  const { counts, state } = platform.health;
  const parts = [
    counts.critical > 0 && `${String(counts.critical)} critical`,
    counts.warning > 0 && `${String(counts.warning)} warning`,
    counts.unknown > 0 && `${String(counts.unknown)} unknown`,
  ].filter(Boolean);
  return (
    <div
      role="group"
      aria-label="Platform state"
      className={`flex min-w-0 items-center gap-4 ${isError ? "text-text-muted" : ""}`}
    >
      <Link to="/" className="truncate font-semibold text-text">
        {platform.name}
      </Link>
      <span aria-live="polite">
        <StatusBadge state={state} />
      </span>
      <span className="truncate text-small text-text-muted max-xl:hidden">
        {parts.length > 0 ? parts.join(", ") : `${String(counts.healthy)} healthy`}
        {isError && " (not refreshed)"}
      </span>
    </div>
  );
}
