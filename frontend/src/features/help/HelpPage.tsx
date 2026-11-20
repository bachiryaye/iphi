import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";

import { SimulatedBanner } from "@/app/AppShell";
import { sections } from "@/shared/help/content";
import { useLanguage } from "@/shared/i18n/context";
import { LanguageSelect } from "@/shared/i18n/LanguageSelect";

export function HelpPage() {
  const { language } = useLanguage();
  const { hash } = useLocation();
  const fr = language === "fr";
  const [contentsOpen, setContentsOpen] = useState(
    () => window.matchMedia("(min-width: 1024px)").matches,
  );
  useEffect(() => {
    if (hash === "") return;
    const target = document.getElementById(hash.slice(1));
    target?.scrollIntoView();
    target?.focus({ preventScroll: true });
  }, [hash]);
  return (
    <>
      <SimulatedBanner />
      <a href="#help-main" className="absolute -top-10 left-2 z-10 bg-surface p-2 focus:top-8">
        {fr ? "Aller au guide" : "Skip to guide"}
      </a>
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border bg-surface px-6 py-4">
        <Link
          to="/"
          className="font-mono font-semibold"
          aria-label={fr ? "IPHI · ouvrir l’application" : "IPHI · open application"}
        >
          IPHI
        </Link>
        <div className="flex flex-wrap items-center gap-5">
          <Link to="/" className="text-accent underline underline-offset-2">
            {fr ? "Ouvrir l’application" : "Open application"}
          </Link>
          <Link to="/login" className="text-accent underline underline-offset-2">
            {fr ? "Se connecter" : "Sign in"}
          </Link>
          <LanguageSelect />
        </div>
      </header>
      <main
        id="help-main"
        tabIndex={-1}
        className="mx-auto grid max-w-[1200px] grid-cols-[220px_minmax(0,1fr)] gap-10 px-6 py-8 max-lg:grid-cols-1 max-lg:gap-6 max-sm:px-4"
      >
        <nav
          aria-label={fr ? "Sommaire du guide" : "Guide contents"}
          className="self-start lg:sticky lg:top-6 lg:max-h-[calc(100dvh-3rem)] lg:overflow-y-auto"
        >
          <details
            open={contentsOpen}
            onToggle={(event) => {
              setContentsOpen(event.currentTarget.open);
            }}
          >
            <summary className="cursor-pointer py-2 font-semibold">
              {fr ? "Sommaire : 16 sujets" : "Contents: 16 topics"}
            </summary>
            <ul className="text-guide-nav">
              {sections[language].map((section) => (
                <li key={section.id}>
                  <Link
                    to={`#${section.id}`}
                    className="block py-1.5 text-text-muted underline-offset-4 hover:text-text hover:underline"
                  >
                    {section.title}
                  </Link>
                </li>
              ))}
            </ul>
          </details>
        </nav>
        <div className="min-w-0 max-w-[70ch] text-guide [overflow-wrap:anywhere]">
          <h1 className="text-guide-title font-semibold">
            {fr ? "Comprendre et utiliser IPHI" : "Understand and use IPHI"}
          </h1>
          <p className="mt-3 mb-6 text-text-muted">
            {fr
              ? "Vous découvrez l’outil ? Commencez par la connexion, puis suivez les six exercices dans l’ordre. Chaque étape indique quoi faire et ce que vous devez voir. Vous pouvez revenir au vocabulaire ou au dépannage à tout moment."
              : "New to the tool? Start with sign-in, then follow the six exercises in order. Each step says what to do and what you should see. Return to vocabulary or troubleshooting whenever you need them."}
          </p>
          <ul className="mb-6 flex flex-wrap gap-x-6 gap-y-2 text-guide-nav">
            {(
              [
                ["start", fr ? "Je découvre IPHI" : "I am new to IPHI"],
                ["scenarios", fr ? "Je veux essayer la démo" : "I want to try the demo"],
                ["troubleshooting", fr ? "Je suis bloqué" : "I need help"],
                [
                  "presentation",
                  fr ? "Je prépare ma présentation" : "I am preparing a presentation",
                ],
              ] as const
            ).map(([id, label]) => (
              <li key={id}>
                <Link
                  to={`#${id}`}
                  className="inline-block py-1 text-accent underline underline-offset-2"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
          <p className="border-l-[3px] border-border-strong bg-surface p-4 text-guide-nav">
            {fr
              ? "La langue choisie est conservée dans ce navigateur. Les identifiants techniques, preuves, journaux et textes produits restent dans leur langue d’origine ; les rapports PDF/CSV restent en anglais."
              : "Your language choice is saved in this browser. Technical identifiers, evidence, logs and generated text keep their original language; PDF/CSV reports remain English."}
          </p>
          {sections[language].map((section, index) => (
            <section key={section.id} className="border-b border-border py-8 last:border-b-0">
              <h2
                id={section.id}
                tabIndex={-1}
                className="scroll-mt-6 text-guide-heading font-semibold"
              >
                {section.title}
              </h2>
              <p className="mt-4 text-pretty">{section.body}</p>
              {section.entries && (
                <dl className="mt-6 space-y-5">
                  {section.entries.map((entry) => (
                    <div key={entry.term}>
                      <dt className="font-semibold">{entry.term}</dt>
                      <dd className="mt-1 text-pretty">{entry.definition}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {section.steps ? (
                <>
                  <h3 id={`${section.id}-steps`} className="mt-6 font-semibold">
                    {fr ? "Pas à pas" : "Step by step"}
                  </h3>
                  <ol
                    aria-labelledby={`${section.id}-steps`}
                    className="mt-4 list-decimal space-y-6 pl-6 marker:font-semibold"
                  >
                    {section.steps.map((step) => (
                      <li key={step.instruction} className="pl-2">
                        <p className="font-medium text-pretty">{step.instruction}</p>
                        <p className="mt-2 text-pretty">
                          <span className="font-medium">
                            {fr ? "Vous devez voir : " : "You should see: "}
                          </span>
                          {step.result}
                        </p>
                      </li>
                    ))}
                  </ol>
                </>
              ) : (
                <p className="mt-6 text-pretty">{section.action}</p>
              )}
              <div className="mt-6 border-l-[3px] border-border-strong bg-surface p-4">
                <h3 className="font-semibold">{fr ? "À retenir" : "Remember"}</h3>
                <p className="mt-2 text-pretty">{section.result}</p>
              </div>
              <div className="mt-6 flex flex-wrap gap-x-6 gap-y-3 text-guide-nav">
                {section.resources?.map((resource) => (
                  <a
                    key={resource.href}
                    href={resource.href}
                    className="py-1 text-accent underline underline-offset-2"
                  >
                    {resource.label}
                  </a>
                ))}
                {section.to !== undefined && (
                  <Link to={section.to} className="py-1 text-accent underline underline-offset-2">
                    {section.view ?? (fr ? "Ouvrir cette vue" : "Open this view")}
                  </Link>
                )}
                {sections[language][index + 1] && (
                  <Link
                    to={`#${sections[language][index + 1]?.id ?? "start"}`}
                    className="py-1 text-accent underline underline-offset-2"
                  >
                    {fr ? "Suite : " : "Next: "}
                    {sections[language][index + 1]?.title}
                  </Link>
                )}
                <Link to="#help-main" className="py-1 text-accent underline underline-offset-2">
                  {fr ? "Revenir au début" : "Back to the beginning"}
                </Link>
              </div>
            </section>
          ))}
        </div>
      </main>
    </>
  );
}
