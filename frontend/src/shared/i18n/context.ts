import { createContext, useContext } from "react";

import { english, type Language, type Translator } from "./translate";

export const LanguageContext = createContext<{
  language: Language;
  setLanguage: (language: Language) => void;
  t: Translator;
}>({ language: "en", setLanguage: () => undefined, t: english });

export const useLanguage = () => useContext(LanguageContext);
export const useT = () => useLanguage().t;
