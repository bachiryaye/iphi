"""Deterministic mock data and SVG for the Component screen (StateBand + metric chart, §6.3).

Scenario: collector-01, window 10:27:07–10:42:07 UTC. A latency hump raises R-LAT-001 to Warning
(INC-0005, auto-resolved), then collector_down #12 stops the service at 10:39:42.
"""
import json
import math

T0, T1 = 10 * 3600 + 27 * 60 + 7, 10 * 3600 + 42 * 60 + 7
GUTTER, RIGHT, WIDTH = 150, 790, 800
CHART_TOP, CHART_BOTTOM, Y_MAX = 136, 286, 1200
LAST_UP = 10 * 3600 + 39 * 60 + 37


def hms(h, m, s=0):
    return h * 3600 + m * 60 + s


def fmt(t):
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def x(t):
    return GUTTER + (t - T0) / (T1 - T0) * (RIGHT - GUTTER)


def y(v):
    return CHART_BOTTOM - v / Y_MAX * (CHART_BOTTOM - CHART_TOP)


def latency_samples():
    seed, out, peak = 12, [], hms(10, 32, 10)
    t = T0
    while t <= LAST_UP:
        seed = (seed * 1103515245 + 12345) % 2**31
        noise = (seed / 2**31 - 0.5) * 14
        hump = 280 * math.exp(-(((t - peak) / 55) ** 2))
        out.append((t, round(62 + noise + hump)))
        t += 5
    return out


ROWS = [
    ("collector-01", "component", 20, [("healthy", T0, hms(10, 31, 46)), ("warning", hms(10, 31, 46), hms(10, 33, 35)),
                                      ("healthy", hms(10, 33, 35), hms(10, 39, 47)), ("critical", hms(10, 39, 47), T1)]),
    ("R-AVAIL-001 v1", "rule", 14, [("healthy", T0, hms(10, 39, 47)), ("critical", hms(10, 39, 47), T1)]),
    ("R-LAT-001 v1", "rule", 14, [("healthy", T0, hms(10, 31, 46)), ("warning", hms(10, 31, 46), hms(10, 33, 35)),
                                  ("healthy", hms(10, 33, 35), hms(10, 40, 42)), ("unknown", hms(10, 40, 42), T1)]),
    ("R-QUEUE-001 v1", "rule", 14, [("healthy", T0, hms(10, 40, 12)), ("unknown", hms(10, 40, 12), T1)]),
    ("R-TEL-001 v1", "rule", 14, [("healthy", T0, T1)]),
]
MARKERS = [("INC-0005 opened", hms(10, 31, 46)), ("INC-0005 resolved", hms(10, 33, 35)), ("INC-0007 opened", hms(10, 39, 47))]
LABELS = {"healthy": "Healthy", "warning": "Warning", "critical": "Critical", "unknown": "Unknown"}


def svg():
    parts = [f'<svg class="hc__svg" viewBox="0 0 {WIDTH} 318" aria-hidden="true">',
             '<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<rect width="6" height="6" class="hc__hatch-bg"/><line x1="0" y1="0" x2="0" y2="6" class="hc__hatch"/></pattern></defs>']
    scen = x(hms(10, 39, 40))
    parts.append(f'<rect class="hc__scenario" x="{scen:.1f}" y="18" width="{RIGHT - scen:.1f}" height="{CHART_BOTTOM - 18}"/>')
    parts.append(f'<text class="hc__scenario-label" x="{RIGHT - 4}" y="{CHART_TOP - 10}" text-anchor="end">collector_down #12</text>')

    top = 22
    for label, kind, h, segs in ROWS:
        cls = "hc__row-label hc__row-label--component" if kind == "component" else "hc__row-label"
        parts.append(f'<text class="{cls}" x="0" y="{top + h / 2 + 4:.1f}">{label}</text>')
        for state, a, b in segs:
            x0, x1 = x(a) + 1, x(b) - 1
            fill = 'url(#hatch)' if state == "unknown" else ""
            fill_attr = f' fill="{fill}"' if fill else ""
            parts.append(f'<rect class="hc__seg hc__seg--{state}" x="{x0:.1f}" y="{top}" width="{x1 - x0:.1f}" height="{h}" rx="2"{fill_attr}/>')
            if state != "healthy" and x1 - x0 >= 56 and kind == "component":
                ty = top + h / 2 + 4
                parts.append(f'<text class="hc__seg-label hc__seg-label--{state}" x="{x0 + 6:.1f}" y="{ty:.1f}">{LABELS[state]}</text>')
        top += h + 2

    for v, name in ((250, "warning"), (1000, "critical")):
        parts.append(f'<line class="hc__threshold" x1="{GUTTER}" x2="{RIGHT}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
        parts.append(f'<text class="hc__axis" x="{GUTTER - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{v} {name}</text>')
    parts.append(f'<line class="hc__baseline" x1="{GUTTER}" x2="{RIGHT}" y1="{CHART_BOTTOM}" y2="{CHART_BOTTOM}"/>')
    parts.append(f'<text class="hc__axis" x="{GUTTER - 8}" y="{CHART_BOTTOM + 4}" text-anchor="end">0 ms</text>')
    parts.append(f'<text class="hc__axis hc__axis--title" x="0" y="{CHART_TOP - 10}">probe_latency_ms</text>')
    parts.append(f'<text class="hc__axis" x="122" y="{CHART_TOP - 10}">raw samples every 5 s, input of R-LAT-001 (p95, 60 s)</text>')

    pts = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in latency_samples())
    parts.append(f'<polyline class="hc__series" points="{pts}"/>')
    gap_x = x(LAST_UP)
    parts.append(f'<text class="hc__gap" x="{RIGHT - 6}" y="{y(420):.1f}" text-anchor="end">No samples since 10:39:37</text>')
    parts.append(f'<line class="hc__gap-edge" x1="{gap_x:.1f}" x2="{gap_x:.1f}" y1="{y(60) - 10:.1f}" y2="{y(60) + 10:.1f}"/>')

    for name, t in MARKERS:
        mx = x(t)
        parts.append(f'<line class="hc__marker" x1="{mx:.1f}" x2="{mx:.1f}" y1="14" y2="{CHART_BOTTOM}"/>')
        parts.append(f'<path class="hc__marker-head" d="M{mx - 4:.1f} 6 h8 l-4 6z"/>')
    for minute in range(28, 43, 2):
        t = hms(10, minute)
        parts.append(f'<text class="hc__axis" x="{x(t):.1f}" y="{CHART_BOTTOM + 20}" text-anchor="middle">10:{minute:02d}</text>')

    parts.append(f'<line class="hc__cursor" x1="0" x2="0" y1="18" y2="{CHART_BOTTOM}" visibility="hidden"/>')
    parts.append("</svg>")
    return "".join(parts)


def data():
    return json.dumps({
        "t0": T0, "t1": T1, "gutter": GUTTER, "right": RIGHT, "width": WIDTH,
        "rows": [{"label": r[0], "segs": [[s, a, b] for s, a, b in r[3]]} for r in ROWS],
        "latency": latency_samples(), "markers": [[n, t] for n, t in MARKERS],
    })


def transitions_table():
    rows = []
    for label, *_, segs in ROWS:
        for prev, cur in zip(segs, segs[1:]):
            rows.append((cur[1], label, LABELS[prev[0]], LABELS[cur[0]]))
    rows.sort()
    body = "".join(
        f'<tr><td class="mono">{fmt(t)}</td><td class="mono">{label}</td><td>{a}</td><td>{b}</td></tr>'
        for t, label, a, b in rows)
    return ('<table class="table hc__table"><thead><tr><th scope="col">Time (UTC)</th><th scope="col">Subject</th>'
            f'<th scope="col">From</th><th scope="col">To</th></tr></thead><tbody>{body}</tbody></table>')
