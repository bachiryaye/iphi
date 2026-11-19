import { useEffect } from "react";
import { Link, useLocation } from "react-router";

import { SimulatedBanner } from "@/app/AppShell";
import { sections } from "@/shared/help/content";
import { useLanguage } from "@/shared/i18n/context";
import { LanguageSelect } from "@/shared/i18n/LanguageSelect";

export function HelpPage() {
  const { language } = useLanguage();
  const { hash } = useLocation();
  const fr = language === "fr";
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
        className="mx-auto grid max-w-[1200px] grid-cols-[220px_minmax(0,1fr)] gap-12 px-6 py-8 max-md:grid-cols-1 max-md:gap-6"
      >
        <nav
          aria-label={fr ? "Sommaire du guide" : "Guide contents"}
          className="self-start md:sticky md:top-6"
        >
          <p className="mb-3 font-semibold">{fr ? "Dans ce guide" : "In this guide"}</p>
          <ol className="flex list-outside list-decimal flex-col gap-1 pl-4 text-small">
            {sections[language].map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  className="block py-1 text-text-muted underline-offset-4 hover:text-text hover:underline"
                >
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <div className="min-w-0 max-w-[74ch]">
          <h1 className="text-display font-semibold">
            {fr ? "Comprendre et utiliser IPHI" : "Understand and use IPHI"}
          </h1>
          <p className="mt-3 mb-6 text-text-muted">
            {fr
              ? "Du premier accès à un rapport étayé. Un parcours guidé sur une plateforme entièrement simulée, sans fournisseur IA obligatoire."
              : "From your first sign-in to an evidence-backed report. A guided journey on a fully simulated platform, with no AI provider required."}
          </p>
          <p className="border-l-[3px] border-border-strong bg-surface p-3 text-small">
            {fr
              ? "La langue choisie est conservée dans ce navigateur. Les identifiants techniques, preuves, journaux et textes produits restent dans leur langue d’origine ; les rapports PDF/CSV restent en anglais."
              : "Your language choice is saved in this browser. Technical identifiers, evidence, logs and generated text keep their original language; PDF/CSV reports remain English."}
          </p>
          {sections[language].map((section, index) => (
            <section key={section.id} className="border-b border-border py-7 last:border-b-0">
              <h2 id={section.id} tabIndex={-1} className="scroll-mt-6 text-heading font-semibold">
                {section.title}
              </h2>
              <p className="mt-3 leading-relaxed">{section.body}</p>
              <dl className="mt-4 flex flex-col gap-2 leading-relaxed">
                <dt className="font-semibold">{fr ? "À faire" : "Try it"}</dt>
                <dd className="text-text-muted">{section.action}</dd>
                <dt className="mt-2 font-semibold">{fr ? "Résultat attendu" : "What to expect"}</dt>
                <dd className="text-text-muted">{section.result}</dd>
              </dl>
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-small">
                {section.to !== undefined && (
                  <Link to={section.to} className="text-accent underline underline-offset-2">
                    {fr ? "Ouvrir cette vue" : "Open this view"}
                  </Link>
                )}
                {sections[language][index + 1] && (
                  <Link
                    to={`#${sections[language][index + 1]?.id ?? "start"}`}
                    className="text-accent underline underline-offset-2"
                  >
                    {fr ? "Étape suivante" : "Next step"}
                  </Link>
                )}
              </div>
            </section>
          ))}
        </div>
      </main>
    </>
  );
}
