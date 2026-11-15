import { useEffect, useState } from "react";

/** Changes whenever the theme attribute flips, so canvas-like renderers re-read the tokens. */
export function useThemeVersion(): string {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? "light");
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setTheme(document.documentElement.dataset.theme ?? "light");
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => {
      observer.disconnect();
    };
  }, []);
  return theme;
}

export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
