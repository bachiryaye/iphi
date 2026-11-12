// Evidence chips highlight the evidence row and the chart point (§6.4, P3).
document.addEventListener("click", function (event) {
  var chip = event.target.closest(".chip[data-ev]");
  if (!chip) return;
  var id = chip.dataset.ev;
  var wasActive = chip.getAttribute("aria-pressed") === "true";

  document.querySelectorAll(".chip[data-ev]").forEach(function (c) {
    c.setAttribute("aria-pressed", String(!wasActive && c.dataset.ev === id));
  });
  document.querySelectorAll(".evidence tr.is-active, .chart__ev.is-active").forEach(function (el) {
    el.classList.remove("is-active");
  });
  if (wasActive) return;

  var row = document.getElementById("ev-" + id);
  if (row) {
    row.classList.add("is-active");
    if (!chip.closest(".evidence")) row.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
  var point = document.querySelector('.chart__ev[data-ev="' + id + '"]');
  if (point) point.classList.add("is-active");
});

// Claim disclosure: reveals the cited evidence in place.
document.addEventListener("click", function (event) {
  var toggle = event.target.closest(".claim__toggle");
  if (!toggle) return;
  var open = toggle.getAttribute("aria-expanded") !== "true";
  toggle.setAttribute("aria-expanded", String(open));
  document.getElementById(toggle.getAttribute("aria-controls")).hidden = !open;
});
