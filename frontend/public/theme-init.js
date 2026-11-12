// Mirrors src/app/theme.ts: stored choice first, then prefers-color-scheme (design system §3.2).
(function () {
  var saved = null;
  try {
    saved = localStorage.getItem("iphi-theme");
  } catch (e) {
    saved = null;
  }
  var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme =
    saved === "dark" || saved === "light" ? saved : dark ? "dark" : "light";
})();
