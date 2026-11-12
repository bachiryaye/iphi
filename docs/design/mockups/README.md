# Maquettes statiques IPHI

Maquettes HTML/CSS des écrans **Overview**, **Incident**, **Component** et de la planche **États d'interface** (design system v1.3). Elles font référence pour US-06 et US-07 ; ce n'est pas du code de production (pas de React, données figées du scénario `collector_down #12`).

## Ouvrir

- Directement : ouvrir `overview.html`, `incident.html`, `component.html` ou `states.html` dans un navigateur.
- Thème : bouton en haut à droite, ou `?theme=dark` / `?theme=light` dans l'URL.
- Interactions démontrées : puces de preuve `E1…E6` (surlignent la ligne et le point du graphique), affirmations du diagnostic dépliables, occurrences regroupées dans la chronologie ; sur Component, réticule commun aux bandes d'état et à la courbe (souris, ou clavier ←/→, Début/Fin après focus sur le graphique) et tableau des transitions (*View as table*).

## Modifier

Les pages sont assemblées à partir de `src/` (barre latérale, barre supérieure et sprite d'icônes partagés) :

```bash
python3 docs/design/mockups/build.py
```

Ne pas éditer les pages générées (`*.html` à la racine du dossier) : modifier `src/` puis reconstruire.

## Contenu

| Chemin | Rôle |
|---|---|
| `src/` | Sources des pages et partiels (`_sidebar.html`, `_topbar.html`, `_icons.svg`) ; `component_chart.py` génère les données déterministes et le SVG de l'écran Component |
| `assets/tokens.css` | Tokens du design system §3 (clair / sombre) |
| `assets/app.css`, `overview.css`, `incident.css`, `component.css`, `states.css` | Coque, composants, écrans |
| `assets/fonts/` | IBM Plex Sans / Mono (SIL OFL 1.1, licence jointe) |
| `assets/LICENSE-carbon-icons.txt` | Icônes d'interface IBM Carbon (Apache-2.0) ; indicateurs d'état dessinés à part |
| `screenshots/` | Captures Playwright 1440 px, clair et sombre |

## Vérification

- Revue contre le design system et axe-core 4.14 (règles WCAG 2.0/2.1/2.2 A–AA + best-practice) : 0 violation sur les quatre pages, thèmes clair et sombre, 1440 et 768 px, ainsi qu'avec l'info-bulle et le tableau de Component ouverts (2026-11-12).
- Non couvert : tri et filtres des tableaux, écrans Topology, Scenarios, Rules, Audit.
