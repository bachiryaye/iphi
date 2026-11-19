import { Link, useLocation } from "react-router";

import { useLanguage } from "@/shared/i18n/context";
import { pageGuidance, pageForPath, type HelpPageKey } from "./pageContent";

export function PageHelp({ page }: { page?: HelpPageKey }) {
  const { pathname } = useLocation();
  const { language } = useLanguage();
  const entry = pageGuidance[page ?? pageForPath(pathname)];
  return (
    <div className="flex flex-col gap-1">
      <details className="rounded-control border border-border bg-surface text-small">
        <summary className="cursor-pointer px-4 py-2 font-medium">
          {language === "fr" ? "Aide pour cette page" : "Help for this page"}
        </summary>
        <div className="flex max-w-[80ch] flex-col gap-2 px-4 pt-1 pb-3">
          <p className="text-text-muted">{entry[language]}</p>
          <Link to={`/help#${entry.topic}`} className="text-accent underline underline-offset-2">
            {language === "fr"
              ? "Guide débutant et prochaine étape"
              : "Beginner guide and next step"}
          </Link>
        </div>
      </details>
      {language === "fr" && (
        <p className="text-small text-text-muted">
          Preuves, journaux et diagnostics : langue d’origine conservée. Rapports : anglais.
        </p>
      )}
    </div>
  );
}
