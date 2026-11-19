# ADR 0027 — Bilingual presentation and beginner help

- Status: Accepted (owner-requested finalization, 2026-11-19)
- Scope: presentation and documentation; supersedes only the English-only UI decision in ADR 0010

## Context

The demonstrator must be usable by a beginner without an accompanying explanation. The owner approved a readable README, an in-app beginner journey, help on every page and French/English switching after US-12. API identifiers and stored evidence must remain stable (D-01, D-07, D-17, A-09).

## Decision

- English remains the initial interface language. A native, explicitly labelled selector on sign-in, the application header and public `/help` chooses EN/FR. The validated preference is stored as `iphi-language` in localStorage; if browser storage is blocked, switching works for the current page. No session credential is stored there.
- A React context carries language and a translator. Changing it updates consumers in place: routing, filters, form values, query caches and sessions are retained. No translation dependency, global mutable locale store, API language parameter or database migration is introduced (A-07, C-22).
- English messages are catalog keys; a centralized French catalog supplies their presentation. Named placeholders support different sentence order. Canonical keys, units, API enum values and stored evidence are never rewritten. Known simulator catalog descriptions have French presentation entries; unknown future server text falls back to its original wording. Arbitrary logs, comments, incident titles, rule explanations and generated diagnoses retain their original language. The French interface states this explicitly; PDF/CSV content remains English.
- Presentation helpers take an optional translator (English by default) so numbers use the selected locale and relative times have translated wording. Absolute timestamps retain the ISO-like UTC format required by the design system; local-time context is translated. Audit remains real wall-clock UTC, separate from simulated platform time (C-25).
- `/help` is available before authentication and contains no private data. A table of contents links ten sections: sign-in/roles, health semantics, fault injection, metrics, incidents, diagnosis, recovery, reports, vocabulary and troubleshooting. Each section has an action and expected result. Native `details`/`summary` supplies short page-specific help and a link to the relevant guide section. Links and selectors work by keyboard (C-26).
- The guide reuses existing IBM Plex typography, tokens and the restrained instrument design. Its navigation and narrow reading column take inspiration from documentation layouts; no external service or branding is added.
- README remains English with a French entry point. Static English/French beginner guides complement the in-app guide; detailed API access, MQTT, performance and diagnosis stay in dedicated documents. Instructions distinguish persistent development history from the disposable demo volume.

## Alternatives

- DOM text replacement: rejected because it would alter stored evidence, miss accessible labels and lose React state consistency.
- Backend translation or translated evidence persistence: rejected because it changes contracts and audit meaning outside this task.
- Translation service/framework: unnecessary for two bundled languages without plurals beyond explicit message forms; no network or recurring cost is needed.

## Validation

Component tests cover both languages, navigation/context links, empty/error/loading/permission states, number/relative-time formatting, preserved evidence, persistence and storage failure. Real-browser checks exercise the beginner journey and locale reload against the actual API. Existing scenario, role and export checks remain authoritative; this change adds no industrial capability or performance claim.
