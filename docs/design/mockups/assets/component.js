// Shared crosshair over StateBand and metric chart (§6.3): pointer and keyboard (← →, Home, End).
(function () {
  var root = document.getElementById("hc");
  var data = JSON.parse(document.getElementById("hc-data").textContent);
  var svg = root.querySelector(".hc__svg");
  var cursor = svg.querySelector(".hc__cursor");
  var tip = root.querySelector(".hc__tip");
  var current = null;
  var LABEL = { healthy: "Healthy", warning: "Warning", critical: "Critical", unknown: "Unknown" };

  function fmt(t) {
    var h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
    return [h, m, s].map(function (n) { return String(n).padStart(2, "0"); }).join(":");
  }
  function xOf(t) { return data.gutter + (t - data.t0) / (data.t1 - data.t0) * (data.right - data.gutter); }
  function stateAt(segs, t) {
    for (var i = 0; i < segs.length; i++) if (t >= segs[i][1] && t < segs[i][2]) return segs[i][0];
    return segs[segs.length - 1][0];
  }
  function latencyAt(t) {
    var best = null;
    data.latency.forEach(function (p) { if (Math.abs(p[0] - t) <= 2.5) best = p; });
    return best;
  }
  function row(label, value, cls) {
    var div = document.createElement("div"); div.className = "hc__tip-row";
    var a = document.createElement("span"); a.textContent = label;
    var b = document.createElement("span"); b.textContent = value; if (cls) b.className = cls;
    div.append(a, b); return div;
  }

  function show(t) {
    t = Math.max(data.t0, Math.min(data.t1 - 1, Math.round(t / 5) * 5 + 2));
    current = t;
    var x = xOf(t);
    cursor.setAttribute("x1", x); cursor.setAttribute("x2", x); cursor.setAttribute("visibility", "visible");

    tip.replaceChildren();
    var head = document.createElement("div"); head.className = "hc__tip-time"; head.textContent = fmt(t) + " UTC";
    tip.append(head);
    data.rows.forEach(function (r) {
      var st = stateAt(r.segs, t);
      tip.append(row(r.label, LABEL[st], st === "healthy" ? "" : "is-" + st));
    });
    var p = latencyAt(t);
    var v = document.createElement("div"); v.className = "hc__tip-value";
    v.textContent = p ? "probe_latency_ms " + p[1] + " ms, sample " + fmt(p[0]) : "probe_latency_ms: no data";
    tip.append(v);

    tip.hidden = false;
    var box = svg.getBoundingClientRect(), scale = box.width / data.width;
    var left = 16 + x * scale + 12;
    if (left + tip.offsetWidth > root.clientWidth - 8) left = 16 + x * scale - tip.offsetWidth - 12;
    tip.style.left = left + "px";
  }
  function hide() { cursor.setAttribute("visibility", "hidden"); tip.hidden = true; }

  svg.addEventListener("pointermove", function (e) {
    var box = svg.getBoundingClientRect();
    var vx = (e.clientX - box.left) / box.width * data.width;
    if (vx < data.gutter || vx > data.right) { hide(); return; }
    show(data.t0 + (vx - data.gutter) / (data.right - data.gutter) * (data.t1 - data.t0));
  });
  svg.addEventListener("pointerleave", hide);
  root.addEventListener("keydown", function (e) {
    var step = e.shiftKey ? 60 : 15;
    if (e.key === "ArrowRight") show((current || data.t0) + step);
    else if (e.key === "ArrowLeft") show((current || data.t1) - step);
    else if (e.key === "Home") show(data.t0);
    else if (e.key === "End") show(data.t1);
    else if (e.key === "Escape") hide();
    else return;
    e.preventDefault();
  });
  root.addEventListener("blur", hide);

  var toggle = document.querySelector('[aria-controls="hc-table"]');
  toggle.addEventListener("click", function () {
    var open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "Hide table" : "View as table";
    document.getElementById("hc-table").hidden = !open;
  });
})();
