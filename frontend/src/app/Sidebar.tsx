import { Dashboard } from "@carbon/icons-react";
import { NavLink } from "react-router";

function BrandMark() {
  return (
    <svg
      viewBox="0 0 28 28"
      width={28}
      height={28}
      aria-hidden="true"
      focusable="false"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      className="flex-none"
    >
      <path d="M15.5 4.5 23.5 12.5" />
      <path d="M23.5 15.5 15.5 23.5" />
      <path d="M12.5 23.5 4.5 15.5" />
      <path d="M4.5 12.5 12.5 4.5" />
    </svg>
  );
}

const NAV_ITEMS = [{ to: "/", label: "Overview", Icon: Dashboard }] as const;

export function Sidebar() {
  return (
    <nav
      aria-label="Main"
      className="sticky top-0 flex h-[calc(100vh-28px)] flex-col border-r border-border bg-surface px-3 py-4 max-lg:px-2"
    >
      <NavLink
        to="/"
        className="flex items-center gap-2.5 px-2 pt-1 pb-5 text-text max-lg:justify-center max-lg:px-0"
      >
        <BrandMark />
        <span className="max-lg:sr-only">
          <span
            translate="no"
            className="block font-mono text-[16px] leading-5 font-semibold tracking-[.04em]"
          >
            IPHI
          </span>
          <span className="block text-micro text-text-muted">Platform Health Intelligence</span>
        </span>
      </NavLink>
      <ul className="flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end
              title={label}
              className="flex h-9 items-center gap-2.5 rounded-control px-2.5 text-text-muted hover:bg-surface-sunken hover:text-text aria-[current=page]:bg-surface-sunken aria-[current=page]:font-medium aria-[current=page]:text-text aria-[current=page]:shadow-[inset_2px_0_0_var(--text)] max-lg:justify-center max-lg:px-0"
            >
              <Icon size={16} aria-hidden="true" />
              <span className="max-lg:sr-only">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="mt-auto border-t border-border px-2 pt-3 text-small text-text-muted max-lg:hidden">
        <span className="inline-flex h-5 items-center rounded-[3px] border border-border-strong px-1.5 font-mono text-micro font-medium tracking-[.03em]">
          SIM
        </span>
        <p className="mt-2">Synthetic telemetry only. No real plant is connected.</p>
      </div>
    </nav>
  );
}
