import type { ReactNode } from "react";

interface CardProps {
  title: string;
  titleId: string;
  meta?: ReactNode;
  children: ReactNode;
  busy?: boolean;
}

export function Card({ title, titleId, meta, children, busy = false }: CardProps) {
  return (
    <section
      aria-labelledby={titleId}
      aria-busy={busy}
      className="min-w-0 rounded-card border border-border bg-surface"
    >
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <h2 id={titleId} className="text-card font-semibold">
          {title}
        </h2>
        {meta !== undefined && (
          <div className="ml-auto flex items-center gap-3 text-small text-text-muted">{meta}</div>
        )}
      </header>
      {children}
    </section>
  );
}
