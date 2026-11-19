import { useEffect, useMemo, useState, type ReactNode } from "react";

import { LanguageContext } from "./context";
import { translator, type Language } from "./translate";

export const LANGUAGE_KEY = "iphi-language";

function savedLanguage(): Language {
  try {
    return localStorage.getItem(LANGUAGE_KEY) === "fr" ? "fr" : "en";
  } catch {
    return "en";
  }
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(savedLanguage);
  const value = useMemo(() => ({ language, setLanguage, t: translator(language) }), [language]);
  useEffect(() => {
    document.documentElement.lang = language;
    document.title = language === "fr" ? "IPHI · Santé de plateforme" : "IPHI · Platform health";
    try {
      localStorage.setItem(LANGUAGE_KEY, language);
    } catch {
      // A blocked browser store still allows switching for this page.
    }
  }, [language]);
  return <LanguageContext value={value}>{children}</LanguageContext>;
}
