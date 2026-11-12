// Theme follows prefers-color-scheme with a remembered manual override (§3.2).
(function () {
  var root = document.documentElement;
  var params = new URLSearchParams(location.search);
  var saved = params.get("theme") || localStorage.getItem("iphi-theme");
  var prefersDark = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = saved || (prefersDark ? "dark" : "light");

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    function sync() {
      var dark = root.dataset.theme === "dark";
      btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      btn.querySelector('[data-theme-icon="light"]').hidden = dark;
      btn.querySelector('[data-theme-icon="dark"]').hidden = !dark;
    }
    btn.addEventListener("click", function () {
      root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem("iphi-theme", root.dataset.theme);
      sync();
    });
    sync();
  });
})();
