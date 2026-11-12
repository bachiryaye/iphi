# ADR 0009 — Pile frontend et design system

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Le design était absent du dossier v1.0 au-delà de principes. Le projet sert de démonstration en recrutement : l'interface doit être crédible pour un public industriel, accessible et cohérente.

## Décision

- React + TypeScript strict + Vite ; Tailwind CSS v4 avec tokens en variables CSS ; shadcn/ui (Radix) copié et adapté ; icônes Carbon (amendement ci-dessous) ; TanStack Query ; React Router ; Apache ECharts ; React Flow + dagre.
- Direction visuelle inspirée des IHM haute performance (ISA-101) : chrome en niveaux de gris, couleur réservée à l'anormal, état par forme + texte + couleur, `Unknown` en pointillé.
- Polices IBM Plex Sans / Mono (OFL), auto-hébergées. Thèmes clair et sombre ; contrastes vérifiés WCAG AA.
- Spécification normative : `docs/04-design-system.md`.

## Alternatives écartées

- Bibliothèque de composants complète (MUI, Ant Design) : aspect générique, personnalisation lourde.
- Recharts : plus simple mais moins adapté aux longues séries avec seuils, bandes et repères.
- uPlot : très performant mais API bas niveau ; envisageable si ECharts s'avère trop lourd.
- Grafana embarqué : ne démontre pas la conception d'un produit et duplique les règles.

## Conséquences

- Coût initial en US-01 (tokens, coque) récupéré à chaque écran.
- Taille du bundle ECharts : import modulaire uniquement des graphiques utilisés.

## Amendement — 2026-11-12 (design system v1.2)

- `lucide-react` est remplacé par `@carbon/icons-react` (Apache-2.0). Motif : Lucide, couplé à shadcn/ui par défaut, est devenu une signature visuelle des interfaces générées ; Carbon est dessiné pour IBM Plex et pour des produits d'entreprise.
- Les états de santé ne passent plus par des icônes de bibliothèque : `StatusIndicator` dessine des formes inspirées du codage redondant des IHM haute performance (Hollifield, *High Performance HMI*, PAS/ISA, fig. 10). L'état Healthy devient neutre.
- shadcn/ui reste la base des primitives (Radix, accessibilité), restylée par les tokens ; aucun style par défaut n'est conservé tel quel.
