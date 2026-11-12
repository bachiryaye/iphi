import { useCallback, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "iphi-theme";

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/** The initial theme is applied by public/theme-init.js before React mounts. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  const toggle = useCallback(() => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage can be disabled; the choice then lasts for this page only.
    }
    setTheme(next);
  }, []);

  return { theme, toggle };
}
