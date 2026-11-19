import { useId } from "react";

import { useLanguage } from "./context";

export function LanguageSelect() {
  const { language, setLanguage } = useLanguage();
  const id = useId();
  return (
    <span className="inline-flex items-center gap-2 text-small">
      <label htmlFor={id}>Français / English</label>
      <select
        id={id}
        name="language"
        value={language}
        onChange={(event) => {
          setLanguage(event.target.value === "fr" ? "fr" : "en");
        }}
        className="min-h-8 rounded-control border border-border-strong bg-surface px-2 text-text"
      >
        <option value="en" lang="en">
          English
        </option>
        <option value="fr" lang="fr">
          Français
        </option>
      </select>
    </span>
  );
}
