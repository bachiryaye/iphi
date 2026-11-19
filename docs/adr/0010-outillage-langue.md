# ADR 0010 — Outillage de développement et langue

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Il faut des installations reproductibles, des vérifications rapides et une langue cohérente pour un public de recrutement potentiellement international.

## Décision

- Python : `uv` + `uv.lock`, Ruff (lint + format), mypy strict, pytest (+ Hypothesis), `structlog` (logs JSON), `import-linter` (contrats de dépendances entre couches, rules.md A-03).
- Frontend : `pnpm` + lockfile, ESLint, Prettier, Vitest, Testing Library, Playwright, axe-core.
- `Makefile` comme point d'entrée unique (`up`, `test`, `lint`, `check`, `demo`).
- CI GitHub Actions : lint, typage, tests, migrations sur PostgreSQL éphémère, dérive du client API, build des images, gitleaks, audits de dépendances.
- Langue : interface, API, code, commits en **anglais** ; documents de conception en **français** ; README en anglais avec résumé français.

## Alternatives écartées

- Poetry / pip-tools : plus lents, `uv` gère aussi la version de Python.
- npm : fonctionne, `pnpm` plus rapide et strict.
- Interface en français : audience plus restreinte ; une internationalisation complète serait du travail non prioritaire.

## Conséquences

- Les termes d'interface sont fixés dans `docs/04-design-system.md` §10.
- Décision réversible : l'interface peut être traduite plus tard (textes centralisés).

## Évolution du 19 novembre 2026

La décision de langue de l’interface est remplacée par l’[ADR 0027](0027-bilingual-help.md) : présentation anglais/français à la demande du propriétaire. API, code et commits restent anglais ; README anglais avec point d’entrée français.
