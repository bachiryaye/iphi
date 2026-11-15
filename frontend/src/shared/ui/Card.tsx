import type { ReactNode } from "react";

interface CardProps {
  title: string;
  titleId: string;
  meta?: ReactNode;
  children: ReactNode;
  busy?: boolean;
  /** Critical cards carry the 3 px left edge of §4. */
  critical?: boolean;
  className?: string;
}

export function Card({
  title,
  titleId,
  meta,
  children,
  busy = false,
  critical = false,
  className = "",
}: CardProps) {
  return (
    <section
      aria-labelledby={titleId}
      aria-busy={busy}
      className={`min-w-0 rounded-card border border-border bg-surface ${
        critical ? "shadow-[inset_3px_0_0_var(--status-critical)]" : ""
      } ${className}`}
    >
      <header className="flex min-h-12 flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-4 py-2.5">
        <h2 id={titleId} className="text-card font-semibold">
          {title}
        </h2>
        {meta !== undefined && (
          <div className="ml-auto flex flex-wrap items-center gap-3 text-small text-text-muted">
            {meta}
          </div>
        )}
      </header>
      {children}
    </section>
  );
}
