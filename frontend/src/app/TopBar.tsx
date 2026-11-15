import { Asleep, Light } from "@carbon/icons-react";

import { Clock } from "./Clock";
import { MonitorStatus } from "./MonitorStatus";
import { PlatformSummary } from "./PlatformSummary";
import { useTheme } from "./theme";

export function TopBar() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";

  return (
    <header className="flex h-15 items-center gap-6 border-b border-border bg-surface px-6 max-lg:px-4">
      <PlatformSummary />
      <div className="ml-auto flex items-center gap-5">
        <MonitorStatus />
        <span aria-hidden="true" className="h-7 w-px bg-border max-md:hidden" />
        <Clock />
        <button
          type="button"
          onClick={toggle}
          aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
          className="inline-grid size-8 cursor-pointer place-items-center rounded-control border border-border bg-surface text-text-muted hover:border-border-strong hover:text-text"
        >
          {dark ? <Light size={16} aria-hidden="true" /> : <Asleep size={16} aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
}
