# ADR 0012 — Génération des rapports PDF

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

US-09 exige un PDF fidèle, cohérent avec l'interface et sûr (contenu échappé).

## Décision

- WeasyPrint : rendu d'un modèle HTML/CSS Jinja2 (auto-échappement activé) utilisant les tokens du design system.
- Dépendances système (Pango) installées dans l'image Docker de l'API.
- CSV via le module standard, cellules neutralisées contre l'injection de formules.

## Alternatives écartées

- ReportLab : pas de dépendance système, mais mise en page codée à la main et incohérente avec l'interface.
- Rendu navigateur headless (Playwright) côté serveur : lourd en production d'image.

## Conséquences

- Image API plus volumineuse (~+60 Mo) ; acceptable pour la démo.
- Contenu du PDF testable via extraction de texte.
