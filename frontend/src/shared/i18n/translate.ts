import { french, type MessageKey } from "./messages";

export type Language = "en" | "fr";
type Values = Record<string, string | number>;
export type Translator = {
  (message: MessageKey, values?: Values): string;
  label: (message: string, values?: Values) => string;
  language: Language;
};
const dictionary: Readonly<Record<string, string>> = french;

export function translator(language: Language): Translator {
  const label = (message: string, values: Values = {}) => {
    const translated =
      language === "fr" && Object.hasOwn(dictionary, message)
        ? (dictionary[message] ?? message)
        : message;
    return translated.replace(/\{(\w+)\}/g, (match, key: string) =>
      Object.hasOwn(values, key) ? String(values[key]) : match,
    );
  };
  return Object.assign(label, { language, label });
}

export const english = translator("en");
