# Inspirations visuelles — moodboard annoté

*IPHI | Préparation des maquettes | 12 novembre 2026*

> Note de travail, non normative : `04-design-system.md` reste la référence. Chaque source est
> analysée au regard des principes P1–P8. Les captures sont stockées localement dans
> `docs/design/moodboard/` et **exclues du dépôt** (`.gitignore`) : ce sont des visuels de produits
> tiers, utilisés uniquement comme référence. On reprend des **patterns**, jamais un look, un nom
> ou une marque.

## Synthèse par écran

| Écran IPHI | À reprendre | Sources |
|---|---|---|
| Overview | Indicateur analogique avec bande « normale » ; valeur normale sans couleur, anormale = icône + trait coloré | GoJS HPHMI (ISA-101), Siemens iX KPI |
| Topology | Graphe au centre + panneau latéral du nœud sélectionné | Kiali |
| Component | Historique d'états en bande horizontale ; sélecteur de fenêtre avec fuseau affiché ; seuils en lignes | Grafana state timeline, Grafana thresholds, Statuspage |
| Incidents (liste) | Indicateur de forme **avant** le libellé, colonne de sévérité alignée | Carbon |
| Incident (détail) | En-tête avec compteurs, barre d'actions, colonne de métadonnées à droite, timeline typée horodatée | Sentry Issue Details, incident.io |
| Diagnostic | Récit en étapes dépliables avec preuve attachée à chaque étape | Sentry Seer (avec réserves) |

## Fiches

### Overview

**`overview-gojs-isa101-hmi.png`**, [GoJS — High-Performance HMI Operator Screen](https://gojs.net/latest/samples/hmiOperatorScreen.html), inspiré d'ISA-101
- Reprendre : l'écran gris signifie « tout va bien » (P1). Les jauges verticales montrent une **plage normale** (bande bleue) et un pointeur pour la valeur. On voit en un coup d'œil si une valeur est dans la norme, sans avoir à la lire. C'est une piste pour la métrique clé de chaque composant, en alternative ou en complément de la sparkline (§6.1).
- Reprendre : le bandeau d'alarmes en tête, avec l'heure, la priorité, le texte et l'action *ACK*. C'est proche de la carte « Active incidents ».
- Écarter : le clignotement à 1 Hz (contraire à P7) et le synoptique façon P&ID, hors sujet pour une plateforme de données.

**`overview-siemens-ix-kpi.png`**, [Siemens iX — KPI](https://ix.siemens.io/docs/components/kpi)
- Reprendre : à l'état nominal, une valeur sans couleur avec un trait neutre. À l'état anormal, une icône devant le libellé et un **trait coloré** sous la valeur. L'unité est en petit, accolée à la valeur. C'est exactement P1 + P2 pour les valeurs de la liste Components.
- Note : iX déconseille d'écrire du texte avec les couleurs de statut et prévoit une couleur de texte « alarme » dédiée. Notre `--status-critical` (5.97:1) est déjà conforme.

**`overview-statuspage-uptime-bars.png`**, [GitHub Status](https://www.githubstatus.com/) (Atlassian Statuspage)
- Reprendre : la bande d'historique (une barre par période), qui raconte la stabilité récente sans graphique.
- Écarter (contre-exemple) : le vert partout et le grand bandeau vert « All Systems Operational ». C'est l'inverse de P1, IPHI garde l'état nominal discret. L'illustration décorative est contraire à P7.

### Topology

**`topology-kiali-graph.png`**, [Istio — Visualizing your mesh (Kiali)](https://istio.io/latest/docs/tasks/observability/kiali/)
- Reprendre : la mise en page graphe + panneau latéral contextuel (résumé du nœud sélectionné, taux d'erreur), avec les filtres et la fenêtre temporelle en barre d'outils. C'est la cible de US-07 (React Flow).
- Écarter : la densité d'icônes de la barre d'outils gauche et les badges de type peu lisibles.

### Component

**`component-grafana-state-timeline.png`**, [Grafana Play — State timeline & Status history](https://play.grafana.org/d/qD-rVv6Mz/state-timeline-and-status-history)
- Reprendre : une **bande d'états par composant ou par règle** sur l'axe du temps, avec le libellé de l'état écrit dans le segment. Ça répond à « depuis quand ? » (§1) et ça rend l'hystérésis visible.
- Écarter (contre-exemple) : la palette arc-en-ciel. Dans IPHI, Healthy reste gris neutre, seuls Warning et Critical sont colorés, et Unknown est **hachuré** (P4), jamais rempli.

**`component-grafana-thresholds.png`**, [Grafana Play — Threshold example](https://play.grafana.org/d/000000167/threshold-example)
- Reprendre : le sélecteur de fenêtre avec le fuseau affiché (« Last 6 hours **UTC** ») et les seuils en lignes horizontales (P6, §7).
- Écarter : les bandes de fond saturées (rouge/orange) sur toute la hauteur. Le §7 demande des bandes « très atténuées » et des seuils pointillés étiquetés.

### Incidents et incident

**`incidents-carbon-severity-table.png`** et **`system-carbon-status-indicators.png`**, [Carbon — Status indicators](https://carbondesignsystem.com/patterns/status-indicator-pattern)
- Reprendre : l'indicateur de forme **avant** le libellé, aligné en colonne. Carbon exige au moins trois éléments parmi icône, forme, couleur et libellé. Le `StatusBadge` du §4 le respecte déjà.
- Reprendre : la distinction entre sévérité calculée (« Automated severity ») et sévérité humaine. Ça s'applique à la sévérité système d'un incident face à son statut d'acquittement.

**`incident-sentry-issue-details.png`**, [Sentry — Issue Details](https://docs.sentry.io/product/issues/issue-details/)
- Reprendre : la structure de page. Un en-tête (titre, composant, compteurs *occurrences*), une barre d'actions (*Resolve*, etc.), une zone principale (preuves) et une **colonne de métadonnées à droite** (first seen / last seen, activité). Le compteur d'événements regroupés illustre la déduplication par fingerprint (scénario 5).
- Écarter : l'histogramme décoratif violet et les intégrations tierces (Jira, Asana).

**`incident-sentry-breadcrumbs-timeline.png`**, Sentry — Breadcrumbs
- Reprendre : une timeline verticale avec une **icône par type d'événement**, l'horodatage absolu aligné à droite, le détail repliable. C'est le modèle de la colonne *Timeline* et de la chaîne de preuves du §6.4.
- Écarter : les horodatages en heure locale sans mention UTC.

**`incident-incidentio-alert-timeline.png`**, [incident.io — Alert timeline](https://docs.incident.io/alerts/alert-timeline)
- Reprendre : la mention explicite « Times shown in BST » en tête de timeline (P6 ; chez nous, « Times shown in UTC »). Le regroupement d'alertes (« Grouping into 1 possible incident ») apparaît comme un événement de la timeline, donc la déduplication est **visible et traçable**.
- Reprendre : le panneau *Details* compact (statut, source, création, priorité) avec des paires clé-valeur.

### Diagnostic

**`diagnosis-sentry-seer-rca.png`**, [Sentry Seer — Root cause analysis](https://docs.sentry.io/product/ai-in-sentry/seer/autofix/)
- Reprendre : le récit en **étapes dépliables**, chaque étape portant sa preuve (fichier, ligne). C'est l'équivalent visuel de nos puces `[E2]`.
- Écarter (point de différenciation) : Seer affirme (« This is the critical bug ») sans séparer fait, hypothèse et incertitude. IPHI rend ces quatre sections visuellement distinctes (§6.4) et liste les affirmations rejetées. C'est l'argument à mettre en avant devant un recruteur.

## Sources non capturées

| Source | Raison |
|---|---|
| Sentry Sandbox | Exige une adresse e-mail pour entrer ; non fournie. Remplacée par la documentation publique. |
| Siemens iX — Event list | Capture masquée par le bandeau cookies ; exemples de doc génériques (« Text 1 »). |
| Kiali — vue Overview | Image de la doc masquée par un bandeau du site. |
| AVEVA PI Vision | Produit propriétaire : volontairement non reproduit (aucune revendication de compatibilité, CDC). |
| Ignition Perspective, Datadog, Dynatrace, PagerDuty | Pas encore consultés, ou démo nécessitant un compte. À compléter si besoin. |

## Pistes retenues

Les trois pistes ont été validées et intégrées au design system v1.1 (2026-11-12) :
1. **Overview** : `RangeMeter` (indicateur de plage, échelle par zones) pour la métrique clé de chaque composant — §6.1.
2. **Component** : `StateBand` (historique d'états par composant et par règle, Healthy neutre, Unknown hachuré) — §6.3.
3. **Incident** : colonne *Details* + `IncidentTimeline` (« Times shown in UTC », occurrences regroupées), affirmations de diagnostic dépliables — §6.4.

## Éviter le « look IA » — sources et décisions

| Source | Ce qu'on en retient | Décision IPHI |
|---|---|---|
| [Hollifield, *High Performance HMI* (PAS / ISA)](https://www.isa.org/getmedia/06130a38-f7af-4b35-8c9c-2c34f25c1977/The-High-Performance-HMI-Overview-v2-01.pdf), fig. 9–10 | Alarmes codées par couleur + forme + texte (P1 carré, P2 triangle, P3 triangle inversé, diagnostic losange) ; couleur réservée à l'anormal ; pas de vert pour « normal » ; gris, 2D, pas d'animation | Indicateurs d'état dessinés (carré / triangle / cercle pointillé) ; Healthy neutre ; compteurs neutres |
| [The Fountain Institute — 7 signs a UI has been vibe coded](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui) | Dégradés violets, lueurs, emojis, cartes imbriquées, barres latérales multicolores, pastilles sans signification | Aucune de ces marques ; une seule barre latérale (Critical) ; cartes non imbriquées |
| [SaaSUI — Why your SaaS UI looks AI-generated](https://www.saasui.design/blog/saas-ui-looks-ai-generated) | Composants par défaut, tous les écrans en tableau de bord, pas de point focal, textes génériques | Mise en page par tâche (Overview ≠ Incident), une action primaire par écran, textes factuels du domaine |
| [Dev.to — Fixing the AI-generated look](https://dev.to/alanwest/how-to-fix-the-ai-generated-look-in-your-frontend-1ahh) | shadcn par défaut + icônes Lucide + Inter = signature reconnaissable | Icônes IBM Carbon, IBM Plex, primitives shadcn entièrement restylées par les tokens |
