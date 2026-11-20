# Three-minute English narration plan

The [published French recording in GitHub’s player](../README.md#recorded-demonstration) is a silent browser walkthrough with written explanations. Its actual chapters, transcript and editing boundaries are in [video-demo.md](video-demo.md). The English script below is an optional narration plan for a separate recording of the wider scripted demo; it is not the soundtrack or a shot-for-shot transcript of the French film.

A recording plan for the IPHI demonstration: what is on screen, what is said, and how long each part lasts. It follows the scripted demo ([demo.md](demo.md)) so the recording shows the application as it runs, on simulated data.

## Before recording

```sh
make demo            # clean stack, scripted acts, collector_down left running in realtime
```

- Browser at 1440 × 900, 100 % zoom, light theme, <http://127.0.0.1:8081> on the Overview.
- A terminal with the output of `make demo` scrolled to the top, font large enough to read.
- Record within a few minutes of the end of `make demo`: the live incident is then recent and the charts show the scripted acts.
- No voice-over claim that is not on screen: nothing about real plants, commercial historians or production use.

## Script

| Time | On screen | Voice-over |
|---|---|---|
| 0:00 – 0:20 | Overview, platform `Critical`. Point at the *SIMULATED DATA* banner. | "This is IPHI. It monitors the health of an industrial data platform: the gateway, collector, historian and APIs that carry process data, rather than the machines. Everything you see runs on a simulated platform of seven components." |
| 0:20 – 0:45 | Terminal: acts 0 and 1 of `make demo`. Highlight the `Critical` line, then "the only active incident". | "One command starts a clean environment and injects faults. Here the collector stops answering. After the rule's confirmation window, a named rule, with its window and its samples, turns it Critical. The components downstream are affected too, yet there is one incident, not four: their alerts are attached to it as impact." |
| 0:45 – 1:15 | Browser, Overview: platform rationale, the `collector-01` row (*DOWN since*), impacted rows, the active incident. Click the incident. | "The same thing in the interface. The platform is Critical because of a priority rule, not an average: one critical collector is not 'eighty-six percent healthy'. Colour is never the only signal; each state has a shape and a label." |
| 1:15 – 1:50 | Incident page: signal chart, evidence chain. Press **Diagnose**; hover an evidence chip so the chain row highlights. | "An incident is only useful with its evidence. Every row here is a stored rule evaluation, sample or log with an ID. The diagnosis is deterministic: observed facts, one hypothesis worded as a correlation, the checks to run. Each claim cites the evidence it rests on. No AI provider is configured; this works without one." |
| 1:50 – 2:20 | Terminal: acts 3 and 4. Then browser, Incidents list filtered on resolved. | "Two cases generic monitoring gets wrong. The historian answers its probe but its data is five minutes old: that is a freshness incident, and the availability rule stays Healthy. Then the historian goes silent: no observation at all gives Unknown, never Healthy. If the monitor's own worker stops, the whole dashboard turns Unknown and says why." |
| 2:20 – 2:40 | Scenarios page: the catalog cards with their expected outcomes; the clock control. Component page of `edge-gateway-01`: latency chart with thresholds from act 2. | "Each scenario announces the outcome to expect, and tests check it. Rules are evaluated on a platform clock, so an accelerated demonstration reaches the same states as a realtime run. Thresholds have separate clear levels: the latency recovery here did not flap." |
| 2:40 – 3:00 | Terminal: `Demo passed in … s`. Then the repository README: **What it demonstrates**, architecture and known limits. | "FastAPI, PostgreSQL, React, one Compose file. The demo is an executable acceptance test, the end-to-end suite replays the same scenarios in a browser, and the limits are written down: simulated data, local sessions and roles, no public deployment. The repository has the design documents and the decision records." |

## Shot list

1. Overview with the live incident (light theme).
2. Terminal, acts 0–1.
3. Incident page before and after **Diagnose**.
4. Terminal, acts 3–4; Incidents list.
5. Scenarios catalog; `edge-gateway-01` latency chart.
6. Terminal, final line; README.

## After recording

`make demo-down` removes the demo stack and its volume.
