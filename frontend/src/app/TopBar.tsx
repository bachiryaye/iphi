import { useT } from "@/shared/i18n/context";
import { Asleep, Light } from "@carbon/icons-react";

import { LanguageSelect } from "@/shared/i18n/LanguageSelect";

import { UserMenu } from "@/features/identity/UserMenu";

import { Clock } from "./Clock";
import { MonitorStatus } from "./MonitorStatus";
import { PlatformSummary } from "./PlatformSummary";
import { useTheme } from "./theme";

export function TopBar() {
  const t = useT();
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";

  return (
    <header className="flex min-h-15 flex-wrap items-center gap-6 border-b border-border bg-surface px-6 max-lg:px-4">
      <PlatformSummary />
      <div className="ml-auto flex flex-wrap items-center justify-end gap-3">
        <MonitorStatus />
        <span aria-hidden="true" className="h-7 w-px bg-border max-md:hidden" />
        <Clock />
        <LanguageSelect />
        <UserMenu />
        <button
          type="button"
          onClick={toggle}
          aria-label={dark ? t("Switch to light theme") : t("Switch to dark theme")}
          className="inline-grid size-8 cursor-pointer place-items-center rounded-control border border-border bg-surface text-text-muted hover:border-border-strong hover:text-text"
        >
          {dark ? <Light size={16} aria-hidden="true" /> : <Asleep size={16} aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
}
