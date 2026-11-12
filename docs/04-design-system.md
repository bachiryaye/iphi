# Design system et expérience utilisateur

**IPHI — Industrial Platform Health Intelligence**

*IPHI  |  Dossier de conception  |  Version 1.3  |  12 novembre 2026*

> Ce document comble un manque du dossier v1.0 : le design n'était spécifié qu'en principes
> (CDC M5). Il est **normatif** pour toute story touchant l'interface
> (DoD interface, backlog §01). Décision associée : ADR 0009.

## 1. Intention

IPHI est un **instrument d'ingénierie**, pas une page SaaS. Un ingénieur doit répondre en moins de cinq secondes à trois questions : *Est-ce que tout va bien ? Sinon, où et depuis quand ? Sur quelles preuves ?*

L'interface doit inspirer confiance à un recruteur du monde industriel : sobre, dense, exacte, honnête sur ce qu'elle ne sait pas.

### Principes

| # | Principe | Conséquence concrète |
|---|---|---|
| P1 | **La couleur signale l'anormal** (inspiré des IHM haute performance, ISA-101) | Fond et chrome en niveaux de gris ; l'état normal est discret ; seuls Warning/Critical attirent l'œil. Pas de vert vif partout. |
| P2 | **Jamais la couleur seule** | Chaque état = forme d'icône + libellé texte + couleur. Lisible en niveaux de gris et pour les daltoniens. |
| P3 | **Chaque affirmation a une preuve** | Partout où un état, un incident ou un diagnostic est affiché, un lien mène à la règle, l'évaluation et les observations. Signature visuelle : les **puces de preuve** `E3`. |
| P4 | **Dire ce qu'on ne sait pas** | `Unknown` a un traitement visuel propre (contour pointillé). Les trous de données restent des trous sur les graphiques. Les données périmées sont signalées. |
| P5 | **Simulé = visible** | Bannière permanente « SIMULATED DATA » et étiquette `source` sur les données ; mention dans les exports. |
| P6 | **Le temps est explicite** | Horloge UTC et locale dans la barre supérieure ; horodatages UTC au survol ; durées relatives (« 4 min ago ») toujours accompagnées de l'heure absolue. |
| P7 | **Pas de mise en scène** | Aucune animation de « faux temps réel », aucun graphique décoratif non relié à des données stockées. Mouvement limité aux transitions utiles (≤ 150 ms), désactivé avec `prefers-reduced-motion`. |
| P8 | **Densité maîtrisée** | Écran de référence 1440 × 900 ; tout l'essentiel de la vue Overview visible sans défilement. |

## 2. Identité

- **Nom affiché :** `IPHI` (mot-symbole en IBM Plex Mono, semi-gras, espacement +4 %), sous-titre « Platform Health Intelligence ».
- **Logo :** monogramme géométrique simple — quatre segments formant un losange, rappel des quatre états de santé. Monochrome, utilisable en favicon 16 px. Aucune ressemblance avec une marque existante.
- **Ton :** factuel, technique, court. On écrit « Collector unreachable for 2 min (R-AVAIL-001) », pas « Oups, quelque chose ne va pas ».

## 3. Tokens

Les tokens sont définis une seule fois (variables CSS consommées par Tailwind) ; aucun composant n'utilise une couleur codée en dur.

### 3.1 Couleurs — thème clair (par défaut si le système est clair)

| Token | Valeur | Usage | Contraste vérifié |
|---|---|---|---|
| `--bg` | `#F3F4F6` | Fond d'application | — |
| `--surface` | `#FFFFFF` | Cartes, panneaux | — |
| `--surface-sunken` | `#E9EBEF` | Zones de graphique, champs | — |
| `--border` | `#D9DCE1` | Séparateurs décoratifs | — |
| `--border-strong` | `#7A8494` | Contours de contrôles | 3.43:1 sur bg ✔ (≥ 3) |
| `--text` | `#1A1F26` | Texte principal | 15.05:1 ✔ |
| `--text-muted` | `#556070` | Texte secondaire | 5.79:1 ✔ |
| `--accent` | `#1F5FBF` | Liens, focus, action primaire | 5.54:1 ✔ |
| `--status-healthy` | `#2E7350` | Réservé (confirmations explicites) ; **pas** utilisé pour l'état Healthy (§4) | 5.18:1 ✔ |
| `--status-warning` | `#8A5A00` | Warning (texte) | 5.39:1 ✔ |
| `--status-warning-fill` | `#F2B13A` | Remplissage du triangle Warning (contour `--status-warning`) | glyphe `--on-warning` 8.77:1 ✔ |
| `--status-critical` | `#B42318` | Critical (texte, remplissage du carré) | 5.97:1 / glyphe blanc 6.57:1 ✔ |
| `--status-unknown` | `#5F6B7A` | Unknown | 4.93:1 ✔ |
| `--on-warning` | `#1A1F26` | Glyphe dans le triangle Warning | 8.77:1 ✔ |
| `--on-critical` | `#FFFFFF` | Glyphe dans le carré Critical | 6.57:1 ✔ |
| `--meter-normal` | `#8A939F` | Bande « normale » du `RangeMeter` | 3.11:1 sur surface ✔ (non-texte) |
| `--band-healthy` | `#DCDFE4` | Segments Healthy du `StateBand` (neutres) | — |
| `--highlight` | `rgba(31,95,191,.10)` | Ligne ou point mis en évidence par une puce de preuve | — |

### 3.2 Couleurs — thème sombre (« control room »)

| Token | Valeur | Contraste vérifié |
|---|---|---|
| `--bg` | `#0E1116` | — |
| `--surface` | `#161B22` | — |
| `--surface-sunken` | `#0B0E12` | — |
| `--border` | `#262C35` | — |
| `--border-strong` | `#67717F` | 3.82:1 ✔ |
| `--text` | `#E6E9EE` | 15.54:1 ✔ |
| `--text-muted` | `#9BA5B2` | 7.58:1 ✔ |
| `--accent` | `#6AAEFF` | 8.21:1 ✔ |
| `--status-healthy` | `#5CB88A` | 7.82:1 ✔ |
| `--status-warning` | `#E8AE3A` | 9.50:1 ✔ |
| `--status-critical` | `#FF7A6E` | 7.44:1 ✔ |
| `--status-unknown` | `#A3ACB8` | 8.24:1 ✔ |
| `--status-warning-fill` | `#E8AE3A` | glyphe `--on-warning` 9.50:1 ✔ |
| `--on-warning` / `--on-critical` | `#0E1116` | 9.50:1 / 7.44:1 ✔ |
| `--meter-normal` | `#606A78` | 3.16:1 sur surface ✔ (non-texte) |
| `--band-healthy` | `#2A313B` | — (`--surface-sunken` était invisible sur la carte : 1.12:1) |
| `--highlight` | `rgba(106,174,255,.18)` | — |

Contrastes calculés selon la formule WCAG 2.x (luminance relative) le 2026-11-12 ; à re-vérifier automatiquement en CI (test des tokens) si une valeur change. Le thème suit `prefers-color-scheme`, avec bascule manuelle mémorisée.

### 3.3 Typographie

| Rôle | Police | Taille / interligne | Usage |
|---|---|---|---|
| Display | IBM Plex Sans 600 | 24 / 32 | Titre de page |
| Heading | IBM Plex Sans 600 | 18 / 26 | Titre de section, carte |
| Body | IBM Plex Sans 400 | 14 / 20 | Texte courant (taille de base) |
| Small | IBM Plex Sans 400 | 12 / 16 | Métadonnées, légendes |
| Data | IBM Plex Mono 400, chiffres tabulaires | 13 / 18 | Valeurs, IDs, horodatages, clés de règle |
| KPI | IBM Plex Mono 500 | 28 / 32 | Valeur principale d'une tuile |

Polices sous licence SIL OFL, auto-hébergées (`@fontsource`), aucun appel à un CDN tiers. Nombres alignés à droite dans les tableaux, unités toujours affichées (`ms`, `%`, `s`, `msg`).

### 3.4 Espacement, formes, élévation

- Grille de 4 px ; espacements usuels 4 / 8 / 12 / 16 / 24 / 32.
- Rayons : 4 px (contrôles), 6 px (cartes). Pas de formes « pilule » pour les états.
- Élévation : bordures plutôt qu'ombres ; une seule ombre légère pour les éléments flottants (menus, panneaux latéraux).
- Focus : anneau 2 px `--accent` avec décalage 2 px, toujours visible au clavier.

## 4. Sémantique des états

Composant unique `<StatusBadge state size />`, utilisé partout (tuiles, tableaux, graphe, rapports PDF). Il associe un **indicateur dessiné** (`StatusIndicator`, SVG maison, pas une icône de bibliothèque) et un libellé. Les formes reprennent le codage redondant des IHM haute performance (B. Hollifield, *High Performance HMI*, PAS/ISA, fig. 10 : couleur + forme + repère texte) : carré pour le plus urgent, triangle pour l'avertissement, cercle pour ce qui n'est pas une alarme.

| État | Indicateur | Libellé | Traitement |
|---|---|---|---|
| Healthy | petit cercle creux en `--border-strong` | `Healthy` en `--text`, graisse normale | **Neutre, jamais vert** : ISA-101 et Hollifield réservent la couleur à l'anormal (P1) |
| Warning | triangle plein `--status-warning-fill`, contour `--status-warning`, « ! » en `--on-warning` | `Warning` en `--status-warning`, semi-gras | — |
| Critical | carré plein `--status-critical`, « ! » en `--on-critical` | `Critical` en `--status-critical`, semi-gras | Bord gauche 3 px sur la carte ou la ligne concernée |
| Unknown | cercle **pointillé** `--status-unknown` avec « ? » | `Unknown` en `--status-unknown`, semi-gras | Info-bulle « No recent evidence since 10:42:05 UTC » |

Pas de pastille pleine colorée : la couleur porte sur la forme et le libellé, comme les indicateurs d'alarme d'une IHM industrielle. Tailles : 14 px (tableaux, listes), 20 px (état de plateforme).

Annotations complémentaires (jamais confondues avec un état) :

- **Impacted** : icône `branch` + texte « Impacted by collector-01 » en `--text-muted`.
- **Stale view** : icône `time` lorsque l'interface affiche des données dont le dernier rafraîchissement a échoué.
- **Simulated** : étiquette `SIM` en Mono, contour fin.

Placement : l'indicateur **précède** toujours son libellé et reste aligné en colonne dans les tableaux ; jamais placé après un texte de longueur variable.

Sévérité d'incident : mêmes indicateurs que Warning/Critical. Statut d'incident : `Open` (point plein), `Acknowledged` (point creux + initiales), `Resolved` (coche, texte atténué). Les compteurs de navigation sont neutres (contour), jamais rouges : le rouge reste réservé aux alarmes.

## 5. Structure de l'application

```text
┌────────────────────────────────────────────────────────────────────────────────┐
│ ▨▨ SIMULATED DATA — synthetic telemetry, not connected to any real plant  ▨▨   │  bannière (hachurée, 28 px)
├──────┬─────────────────────────────────────────────────────────────────────────┤
│ IPHI │ Demo Plant Data Platform   ■ Critical  1 critical, 3 warning, 3 imp. │     │
│      │                       Monitor ● ok · cycle 5s · LLM off   10:42:07 UTC  │  barre supérieure
│ ◉ Ov │                                                    11:42:07 local  ☾    │
│ ⌗ To ├─────────────────────────────────────────────────────────────────────────┤
│ ⚠ In │                                                                         │
│ ▣ Co │                         zone de contenu                                 │
│ ▶ Sc │                                                                         │
│ ≡ Ru │                                                                         │
│ ⎙ Au │                                                                         │
└──────┴─────────────────────────────────────────────────────────────────────────┘
 Navigation : Overview · Topology · Incidents · Components · Scenarios · Rules · Audit (admin)
```

- Barre latérale repliable (icônes + libellés, 64 / 220 px). La barre supérieure affiche **toujours** l'état de la plateforme et l'état du moniteur lui-même (worker, dernier cycle, fournisseur IA) : le moniteur ne peut pas échouer silencieusement.
- Responsive : référence ≥ 1280 px ; tablette ≥ 768 px (barre latérale repliée, grilles sur 2 colonnes) ; mobile en lecture seule (Overview et Incidents).
- Routage : chaque vue et chaque filtre a une URL partageable.

## 6. Écrans

### 6.1 Overview

```text
┌─ Platform health ──────────────────────────────┐ ┌─ Active incidents (2) ──────────────────┐
│ ■ Critical                      since 10:39:47Z │ │ ■ INC-0007 collector-01 unreachable     │
│ Rule: a high-criticality component is Critical │ │   availability · open · 2m 15s · E×6    │
│ ○ 3 Healthy  ▲ 3 Warning  ■ 1 Critical  ◌ 0 Unk│ │ ▲ INC-0006 data-api-01 error burst      │
│ 3 components impacted                          │ │   errors · acknowledged (JD) · 14m      │
└────────────────────────────────────────────────┘ └─────────────────────────────────────────┘
┌─ Components ─────────────────────────────────────────────────────────────────────────────────┐
│ Component        State        Crit. Key metric                                     Last obs │
│ plc-sim-01       ○ Healthy   high  probe latency  ▓▓▓●▓▓▓▓▓▓▓▓▓▓▓▓╎·····╎····    42 ms  2 s │
│ edge-gateway-01  ○ Healthy   high  probe latency  ▓▓▓▓●▓▓▓▓▓▓▓▓▓▓▓╎·····╎····    61 ms  2 s │
│ collector-01     ■ Critical  high  up             DOWN since 10:39:47Z (R-AVAIL-001)    2 s │
│ historian-01     ▲ Warning ⑂ high  data age       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓╎·●···╎····  ▲ 148 s  2 s │
│ timeseries-db-01 ○ Healthy   high  cpu            ▓▓▓▓▓●▓▓▓▓▓▓▓▓▓▓╎·····╎····     31 %  2 s │
│ data-api-01      ▲ Warning ⑂ med.  errors (60 s)  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓╎·●···╎····      ▲ 8  2 s │
│ analytics-01     ▲ Warning ⑂ low   data age       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓╎·●···╎····  ▲  95 s  2 s │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
  ▓ normal range   ● current value   ╎ warning / critical threshold   ┄ no recent value (Unknown)
```

Chaque ligne mène à la vue Component ; chaque incident à la vue Incident.

#### Indicateur de plage (`RangeMeter`)

Inspiré des indicateurs analogiques des IHM haute performance : on lit **où se situe la valeur par rapport à la normale** avant de lire le chiffre.

- **Métrique clé** : choisie **par l'API** (jamais par le frontend) — la métrique de la règle au pire état du composant ; à défaut, la métrique par défaut du type (`source`, `gateway`, `api` → `probe_latency_ms` ; `collector` → `queue_depth` ; `historian`, `analytics` → `data_age_s` ; `database` → `cpu_pct`). La disponibilité (`up`) n'est jamais une jauge : elle s'affiche en texte (`DOWN since …`).
- **Géométrie** : piste 120 × 6 px, rayon 3 px, `--surface-sunken`. Plage normale (du minimum d'affichage au seuil Warning) en `--border`, pleine hauteur. Seuils : traits verticaux de 1 px en `--text-muted`, Warning court (10 px), Critical long (14 px) — distingués par la **forme**, pas par la couleur (P1). **Échelle par zones**, comme les indicateurs HPHMI : zone normale (`display_min` → seuil Warning) sur 60 % de la piste, zone Warning sur 20 %, zone Critical (seuil Critical → `display_max`) sur 20 % ; linéaire à l'intérieur de chaque zone. La résolution est ainsi maximale là où l'opérateur lit les écarts ; le chiffre affiché reste la valeur exacte. Bornes et seuils fournis par l'API (`display_max` par défaut : 1,25 × seuil Critical).
- **Valeur** : pointeur rond de 8 px avec anneau de 2 px en `--surface`. Couleur selon l'**état renvoyé par l'API** (jamais déduite de la position) : `--text` si Healthy, `--status-warning` / `--status-critical` sinon. Hors échelle : pointeur collé à l'extrémité + chevron `›` ; le chiffre reste exact.
- **Chiffre** : à droite, IBM Plex Mono chiffres tabulaires, unité accolée. Nominal en `--text` sans couleur ; anormal précédé de l'icône d'état et coloré du token texte de l'état.
- **Unknown / pas de valeur récente** : piste en contour pointillé, sans pointeur, texte « no data » ; info-bulle « No value since 10:42:05 UTC ».
- **Accessibilité** : `role="meter"`, `aria-valuemin/max/now`, `aria-valuetext` = « 42 ms, normal below 250 ms, Healthy ». La jauge complète le chiffre, elle ne le remplace jamais.
- **Info-bulle** (survol et focus) : valeur, unité, `observed_at` UTC, plage normale, seuils, règle et version, source.
- **Interdit** : jauges circulaires, remplissage façon « réservoir » (une latence n'est pas une quantité consommée), zones colorées en fond de piste.

### 6.2 Topology

Graphe orienté de gauche à droite, dans le sens du flux de données (`plc-sim → gateway → collector → historian → api → analytics`, base de données reliée à l'historian). Nœuds = carte compacte (nom, type, `StatusBadge`, criticité) ; arêtes : trait plein (data_flow) ou pointillé (runtime) ; arêtes en aval d'un composant en défaut tracées en `--status-critical` atténué avec la mention « impact ». Légende permanente. En US-06 : disposition fixe ; en US-07 : React Flow interactif (zoom, sélection ⇒ panneau latéral).

### 6.3 Component

```text
■ Critical  collector-01  since 10:39:47 UTC                                  [Open incident INC-0007]
Type collector │ Criticality high │ Reason R-AVAIL-001 v1 probe not answered │ Last observation 10:42:05 UTC │ SIM

┌ Health over time ─── [latency|queue|up] [15m|1h|6h|24h] UTC ┐ ┌ Dependencies ──── data flow ──────┐
│                       ▾INC-0005      ▾          ▾INC-0007   │ │ Upstream                           │
│ collector-01   ░░░░░░░░▓Warning▓░░░░░░░░░░░░░░░█ Critical █ │ │ ○ edge-gateway-01        gateway   │
│ R-AVAIL-001 v1 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██████████ │ │ ■ collector-01    this component   │
│ R-LAT-001 v1   ░░░░░░░░▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░╱╱╱╱╱ │ │ Downstream, impacted               │
│ R-QUEUE-001 v1 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░╱╱╱╱╱╱ │ │ ▲ historian-01           direct    │
│ R-TEL-001 v1   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ │   ▲ data-api-01   via historian-01 │
│ probe_latency_ms  raw 5 s, input of R-LAT-001   collector_down #12│   ▲ analytics-01  via data-api-01  │
│ 1000 critical ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │ └────────────────────────────────────┘
│                                       No samples since 10:39:37 ┌ Incidents ──────────── last 24 h ┐
│  250 warning  ┄┄┄┄┄┄┄┄╱╲┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │ │ ■ INC-0007 unreachable     ● Open  │
│    0 ms       ───────╱  ╲──────────────────────────│ (gap)  │ │ ▲ INC-0005 latency    ○ Resolved   │
│               10:28  10:30  10:32  10:34  10:36  10:38  10:40 │ └────────────────────────────────────┘
│ ░ Healthy ▲ Warning █ Critical ╱ Unknown ┆ incident   [View as table] │
└─────────────────────────────────────────────────────────────┘
┌ Rules ───────────────────────────── Evaluated every 5 s ────┐
│ State     Rule            Condition                 Observed   Debounce  Since     Evaluation │
│ ■ Critical R-AVAIL-001 v1 last(up, 10 s) < 1         0          raised 2/2 10:39:47 #8812      │
│ ◌ Unknown  R-LAT-001 v1   p95(latency, 60 s) > 250  no samples —         10:40:42  #8851      │
│ ◌ Unknown  R-QUEUE-001 v1 last(queue, 30 s) > 1000  no samples —         10:40:12  #8839      │
│ ○ Healthy  R-TEL-001 v1   any observation in 15 s   2 s ago    —         10:12:00  #8873      │
│ Unknown means the rule had no evidence in its window. It is never counted as Healthy.       │
└─────────────────────────────────────────────────────────────┘
┌ Recent logs ─── warning and above, grouped by fingerprint ──┐
│ 10:39:46  ERROR  connection refused by upstream gateway   12  a91c4e02 │
│ 10:39:41  WARN   upstream read timeout after 5000 ms       3  5be0d771 │
│ No log received since 10:39:46 UTC: the service stopped answering.     │
└─────────────────────────────────────────────────────────────┘
```

- **En-tête** : état du composant (indicateur 20 px), nom, depuis quand, raison (règle déclenchante) et lien direct vers l'incident ouvert, seule action primaire de l'écran.
- **Colonne latérale** : *Dependencies* (amont, le composant lui-même, aval impacté avec la transitivité « via … ») et *Incidents* des dernières 24 h (ouverts et résolus).
- **Rules** : une ligne par règle applicable avec condition, valeur observée, anti-rebond, depuis, évaluation (lien). Une règle sans données est **Unknown** avec la mention « no samples in window », jamais Healthy.
- **Recent logs** : sévérité ≥ warning, regroupés par empreinte avec compteur ; l'absence de logs est expliquée quand elle est significative.

#### Historique d'états (`StateBand`)

Répond à « depuis quand ? » et rend l'hystérésis visible : on voit qu'un état ne bascule pas à chaque échantillon.

- **Lignes** : une ligne pour l'état agrégé du composant (20 px de haut), puis une ligne par règle applicable (14 px), séparées de 2 px. Libellés à gauche dans une colonne de 150 px (clé et version en Mono).
- **Axe partagé** : même fenêtre, même axe des temps et même réticule synchronisé que le graphique de métrique situé dessous. Le sélecteur de fenêtre (avec fuseau affiché, « UTC ▾ ») est unique pour le panneau.
- **Remplissages** : Healthy = `--band-healthy` (**neutre, jamais vert**, P1) ; Warning = `--status-warning-fill` ; Critical = `--status-critical` ; Unknown = `--surface` hachuré à 45° en `--status-unknown` (traits de 1 px espacés de 6 px), bordures haute et basse pointillées (P4). Le hachurage est ici une **sémantique d'état**, pas une texture décorative : il est toujours actif.
- **Libellés** : sur la ligne du composant uniquement, dans un segment non Healthy d'au moins 56 px, nom de l'état (`--on-critical` sur Critical, `--on-warning` sur Warning). Lignes de règles sans libellé interne (trop fines) : l'info-bulle et le tableau donnent l'état.
- **Données** : segments calculés **par le serveur** (état, début, fin, IDs d'évaluation). En sous-échantillonnage, chaque intervalle prend le **pire** état (Critical > Warning > Unknown > Healthy) : un Critical bref n'est jamais masqué. Largeur minimale d'affichage 2 px.
- **Repères** : ouverture/résolution d'incident (triangles verticaux partagés avec le graphique) ; exécution de scénario en accolade sous les bandes (« SIM collector_down #12 »).
- **Interaction** : réticule vertical commun aux bandes et au graphique ; info-bulle (survol et focus) listant l'instant UTC, l'état de chaque ligne et la valeur de la métrique (ou « no data »). Clavier : ←/→ par pas de 15 s (Maj : 60 s), Début/Fin, Échap. Clic sur un segment ⇒ filtre la table des évaluations (US-07).
- **Équivalent textuel** : bouton « View as table » ⇒ liste des transitions (horodatage, de → vers, règle, évaluation).

### 6.4 Incident (écran signature)

```text
■ Critical  INC-0007 collector-01 unreachable          [Acknowledge] [Resolve…] [Diagnose] [Export ▾]
Status ● Open │ Failure class availability │ Opened 10:39:47 UTC 2 min 20 s ago │ Occurrences 24 │ SIM

┌ Probe result  collector-01 up ── [15m] [1h] [6h] [24h] UTC ┐ ┌ Details ──────────────────────────┐
│ up 1  ──────────────────────────────────┐ ░collector_down #12│ │ Status         ● Open             │
│                           INC-0007 opened┆░                 │ │ Severity       ■ Critical         │
│ down 0                                E1 ●●E2 ─────────── ●E6│ │ Component      collector-01 high  │
│       10:30   10:32   10:34   10:36   10:38   10:40   10:42 │ │ Failure class  availability       │
└────────────────────────────────────────────────────────────┘ │ First seen     10:39:47 UTC       │
┌ Evidence chain ───────────────────── 6 items, immutable ───┐ │ Last seen      10:42:02 UTC       │
│ Rule R-AVAIL-001 v1 → Evaluation #8812 → Samples [E1][E2]  │ │ Occurrences    24                 │
│ E1  metric  up = 0                collector-01  10:39:42 SIM│ │ Fingerprint    3f2a9c71  ⧉        │
│ E2  metric  up = 0                collector-01  10:39:47 SIM│ │ Scenario run   collector_down #12 │
│ E3  log     ERROR conn refused ×12 collector-01 10:39:46 SIM│ │ Impacted       historian-01 +2    │
│ E4  impact  data_age_s = 148      historian-01  10:42:04 SIM│ ├ Timeline ──── Times shown in UTC ─┤
│ E5  impact  data_age_s = 95       analytics-01  10:42:04 SIM│ │ 10:39:47 ■ Opened as Critical     │
│ E6  metric  up = 0 (latest)       collector-01  10:42:02 SIM│ │ 10:39:52 ≡ 23 occurrences grouped▾│
└────────────────────────────────────────────────────────────┘ │ 10:40:12 ⑂ historian-01 suppressed│
┌ Diagnosis  Deterministic ─── Generated 10:41:10 UTC ───────┐ │ 10:40:31 ⑂ analytics-01 suppressed│
│ Facts        collector-01 did not answer 24 consecutive    │ │ 10:41:10 ⌕ Diagnosis added, J. Doe│
│              probes               [E1][E2][E6]          ▾  │ └───────────────────────────────────┘
│ Hypotheses   collector-01 is the most upstream failing     │
│              component; downstream freshness degradation   │
│              is correlated, causation not proven           │
│              Uncertainty: low     [E2][E4][E5]          ▾  │
│ Checks     1 Verify collector-01 process            [E1]   │
│            2 Check the link to edge-gateway-01      [E3]   │
│ Limitations  Simulated environment; no host-level metrics  │
└────────────────────────────────────────────────────────────┘
```

- **Probe result** : graphique du signal de la règle déclenchante (ici `up`, en escalier), avec repère d'ouverture d'incident, bande du scénario et points de preuve (`E1`, `E2`, `E6`) que les puces mettent en évidence.
- **Disposition** : colonne principale (signal, preuves puis diagnostic, le contenu qu'on lit) et colonne latérale droite de 320 px, collante au défilement (*Details* puis *Timeline*, le contexte qu'on consulte). En dessous de 1 280 px, la colonne latérale passe sous l'en-tête, *Details* replié sur une ligne et *Timeline* après le diagnostic.
- **Details** : paires clé–valeur alignées (clé en `--text-muted`, valeur en Mono pour les IDs et horodatages) ; empreinte copiable ; composants impactés en liens.
- Les sections FACTS / HYPOTHESES / CHECKS / LIMITATIONS ont chacune un style distinct (faits en texte normal, hypothèses en italique avec niveau d'incertitude, vérifications en liste d'actions, limites en encadré atténué). Chaque affirmation est **dépliable** (bouton `aria-expanded` distinct des puces, jamais de puce dans un `<summary>`) : elle révèle en ligne les preuves citées (type, valeur, horodatage, source) sans quitter la page.
- Les **puces de preuve** `[E2]` sont cliquables : elles surlignent la ligne dans la chaîne de preuves et, pour une métrique, le point sur le graphique.
- Diagnostic IA (US-08) : même mise en page, en-tête « AI-generated · provider/model · verify against evidence », affirmations rejetées listées dans un encadré « Removed: unsupported by evidence ».

#### Chronologie d'incident (`IncidentTimeline`)

- **En-tête** : « Times shown in UTC » ; heure locale et date complète en info-bulle (P6). Séparateur de date quand le jour change.
- **Ligne** : heure absolue `HH:MM:SS` (Mono, alignée à gauche), icône du type d'événement sur un filet vertical continu, libellé court, acteur (`system` ou nom). Détail (payload, commentaire) repliable.
- **Icônes par `event_type`** (Carbon) : `opened` et `severity_changed` → indicateur d'état atteint (§4) ; `occurrence` `layers` ; `acknowledged` `user--follow` ; `commented` `chat` ; `resolved` `checkmark--outline` ; `reopened` `renew` ; `downstream_suppressed` `branch` ; `diagnostic_added` `document--view`. Icônes en `--text-muted`.
- **Déduplication visible** : les événements `occurrence` consécutifs sont regroupés en une ligne « N occurrences grouped » avec la plage temporelle ; dépliée, elle liste chaque occurrence. C'est la preuve visuelle qu'aucune tempête d'incidents n'a eu lieu (scénario 5).
- **Ordre** : chronologique, du plus ancien au plus récent ; un nouvel événement reçu par SSE s'ajoute en bas avec une mise en évidence de 150 ms (désactivée avec `prefers-reduced-motion`) et une annonce `aria-live="polite"`.
- Liste sémantique (`<ol>`) ; chaque ligne est atteignable au clavier quand elle est dépliable.

### 6.5 Scenarios

Catalogue en cartes : nom, description, cible par défaut, **résultat attendu** (état, incident), paramètres bornés, bouton *Start* ; panneau des runs actifs avec *Stop* ; contrôle d'horloge (mode, vitesse, *Advance 30 s* en mode manuel) ; *Reset* (admin, avec confirmation dans l'interface — pas de boîte de dialogue native). Ce panneau est le fil conducteur de la démonstration.

### 6.6 Incidents, Rules, Audit

- **Incidents** : tableau dense (sévérité, ID, composant, classe, statut, ouvert depuis, dernière occurrence, occurrences, preuves), filtres dans l'URL, tri stable, pagination par curseur.
- **Rules** : catalogue en lecture seule (clé, version, type, seuils warning/critical et retours, fenêtre, raise/clear, justification, recommandation).
- **Audit** (admin, US-11) : horodatage, acteur, action, cible, résultat (`allowed`/`denied`/`failed`), `correlation_id`.

## 7. Visualisation de données

- Bibliothèque : **Apache ECharts** (ADR 0009). Lignes sans lissage, points visibles quand la densité le permet.
- **Trous :** aucune interpolation au-delà de 2 intervalles de collecte ; un trou est rendu comme un trou, avec info-bulle « no data ».
- Seuils Warning/Critical en lignes pointillées étiquetées ; bandes de fond très atténuées ; repères verticaux pour l'ouverture/résolution d'incidents et le début/fin des scénarios.
- Axe des temps en UTC par défaut (bascule locale), unités sur l'axe Y, info-bulle : valeur, unité, qualité, `observed_at` UTC, source, ID.
- Sous-échantillonnage côté serveur (min/avg/max par intervalle) : l'interface affiche la plage min–max, pas une moyenne qui masquerait un pic.
- Palette des séries : niveaux de gris + `--accent` ; les couleurs d'état ne servent qu'aux états.
- Un seul axe Y par graphique ; deux mesures d'échelles différentes ⇒ deux graphiques alignés sur le même axe des temps.
- Chaque graphique ou bande a un équivalent textuel (tableau ou liste de transitions) ; l'info-bulle enrichit, elle n'est jamais le seul accès à une valeur.
- Formes spécifiques : `RangeMeter` (§6.1) et `StateBand` (§6.3). Jauges circulaires, camemberts et palettes arc-en-ciel sont exclus.

## 8. États d'interface

Référence visuelle : `docs/design/mockups/states.html`. Règle commune : les états de l'**interface** (chargement, erreur, dégradé…) restent **neutres** ; le rouge et l'ambre sont réservés aux états de la **plateforme** surveillée (P1). Seule exception : le moniteur bloqué, qui est une alarme sur l'instrument lui-même.

| État | Traitement | Exemple de texte |
|---|---|---|
| Chargement | Squelettes statiques à la forme du contenu (pas de spinner plein écran, pas d'animation), `aria-busy` | — |
| Vide | Ce qui est vide, pourquoi, quoi faire ; jamais présenté comme un succès (pas de vert, pas de coche) | « No active incidents. 7 components are evaluated every 5 s… » + *Open scenarios* |
| Erreur | Ce qui a échoué, ce qui continue de fonctionner, *Retry*, `correlation_id` copiable, heure ; icône neutre | « Could not load incidents. The API answered 500 INTERNAL_ERROR. Detection continues on the server; only this list is not updating. » |
| Dégradé | Bandeau persistant neutre (bord gauche 3 px `--border-strong`) au-dessus du contenu, avec le mode de mise à jour de repli | « Live updates paused. Reconnecting…; this page refreshes every 30 s meanwhile. » / « AI diagnosis unavailable… Deterministic diagnosis remains available. » |
| Périmé | Icône `time` + heure et âge des données + prochaine tentative ; contenu en `--text-muted` sur fond hachuré léger | « Data from 10:40:07 UTC, 2 min old. Refresh failed twice; retrying in 10 s. » |
| Permission | Actions visibles mais désactivées, raison en texte visible (rôle courant et rôle requis) ; refus serveur en toast avec code et mention de l'audit (US-11) | « Signed in as j.smith, role viewer. Acknowledge, Resolve and Diagnose require the engineer role. » |
| Moniteur bloqué | Barre supérieure : indicateur Critical + « Monitor stalled », heure du dernier cycle et cadence attendue ; la plateforme passe **Unknown** | « Monitor stalled — last cycle 10:41:20, expected every 5 s » |
| Plateforme Unknown | Carte *Platform health* en Unknown avec la règle (R-TEL-001), la durée sans observation et la vérification suggérée | « No observation received from 7 components for 30 s (R-TEL-001). » |

## 9. Accessibilité (WCAG 2.2 AA)

- Contrastes : §3 ; vérification automatique des tokens en CI.
- Navigation complète au clavier, ordre de tabulation logique, lien d'évitement « Skip to content ».
- Composants interactifs basés sur Radix (via shadcn/ui) pour la gestion du focus et des rôles ARIA.
- Graphiques : titre et résumé textuel accessibles (valeur courante, min/max, seuils), tableau de données alternatif.
- Nouveaux incidents annoncés via `aria-live="polite"` ; pas de son, pas de clignotement.
- Tests axe dans Vitest et Playwright ; aucune violation `serious`/`critical` tolérée.

## 10. Rédaction

- Interface en anglais (ADR 0010). Phrases courtes, verbes d'action sur les boutons (*Acknowledge*, *Resolve*, *Start scenario*).
- Vocabulaire fixe : *component*, *platform*, *incident*, *evidence*, *rule*, *evaluation*, *scenario run*, *impacted*. Jamais « alert » et « incident » comme synonymes.
- Dates : `2026-11-12 10:42:07 UTC` ; relatif toujours doublé de l'absolu (info-bulle).
- On ne surestime jamais : « correlated with », pas « caused by », sauf preuve explicite.

## 11. Mise en œuvre

| Besoin | Choix |
|---|---|
| Styles | Tailwind CSS v4 + variables CSS (tokens §3) |
| Composants | shadcn/ui (Radix), copiés dans `frontend/src/shared/ui`, adaptés aux tokens |
| Icônes | `@carbon/icons-react` (Apache-2.0, grille 16/32 px, dessinées pour IBM Plex) ; indicateurs d'état dessinés (`StatusIndicator`, §4). Pas de Lucide : signature visuelle des interfaces générées. |
| Données serveur | TanStack Query (cache, invalidation SSE) |
| Routage | React Router |
| Graphiques | Apache ECharts |
| Graphe de dépendances | React Flow (`@xyflow/react`) + disposition dagre |
| Tests | Vitest, Testing Library, axe-core, Playwright |

Organisation : `shared/ui` (primitives), `shared/status` (`StatusIndicator`, `StatusBadge`, `EvidenceChip`, `Timestamp`, `MetricValue`, `RangeMeter`, `StateBand`, `IncidentTimeline`), `features/<overview|topology|components|incidents|scenarios|rules|audit>`. Les composants n'implémentent **aucune règle de santé** : ils affichent ce que l'API calcule et justifie.

### Contrats d'API requis par l'interface

Ces visuels n'affichent que des données calculées par le serveur ; ils supposent deux enrichissements **additifs** (sans rupture), reportés dans l'architecture §04.1 :

| Besoin | Contrat | Story |
|---|---|---|
| `RangeMeter` | `GET /api/v1/components` : chaque élément inclut `key_metric` {`name`, `unit`, `value`, `observed_at`, `display_min`, `display_max`, `warning_threshold`, `critical_threshold`, `rule_key`, `rule_version`, `state`} ; `null` si aucune valeur récente | US-06 |
| `StateBand` | `GET /api/v1/components/{id}/state-history?from&to&max_segments` : segments {`state`, `from`, `to`, `evaluation_ids`} pour le composant et pour chaque règle ; pire état par intervalle en sous-échantillonnage | US-07 |

## 12. Revue visuelle

- **US-01 :** coque, tokens, thèmes, bannière et page `/ready` validés visuellement (capture clair/sombre).
- **Maquettes :** Overview, Incident, Component et États d'interface en HTML statique dans `docs/design/mockups/` (captures dans `screenshots/`), revues contre ce document et avec axe-core (0 violation WCAG 2.2 AA sur 16 combinaisons pages × thèmes × 1440/768 px, plus les états interactifs). Elles font référence pour US-06 et US-07.
- **US-06 :** revue des six écrans sur données réelles du simulateur, à 1440 × 900 et 768 px.
- **US-10 :** captures du README régénérées depuis l'application réelle (Playwright), jamais retouchées.

## 13. Historique

| Version | Date | Changement |
|---|---|---|
| 1.0 | 2026-11-12 | Version initiale (ADR 0009). |
| 1.3 | 2026-11-12 | Maquettes Component et États d'interface : §6.3 réécrit (en-tête, *Health over time* avec réticule commun et clavier, règles, logs, dépendances, incidents), lignes de règles à 14 px sans libellé interne, token `--band-healthy`, §8 réécrit (états d'interface neutres, moniteur bloqué, plateforme Unknown). |
| 1.2 | 2026-11-12 | Maquettes : indicateurs d'état d'après Hollifield (carré / triangle / cercle pointillé, plus de pastilles pleines), Healthy neutre, icônes Carbon au lieu de Lucide, compteurs neutres, tokens `--on-*`, `--meter-normal`, `--highlight`, graphique *Probe result* sur Incident, exemples ASCII alignés sur les maquettes (data-api-01 en Warning via R-ERR-001, INC-0007 non acquitté). |
| 1.1 | 2026-11-12 | Après l'étude d'inspirations (`design/inspirations.md`) : `RangeMeter` sur Overview, `StateBand` sur Component, Incident en deux colonnes avec *Details* + `IncidentTimeline` (déduplication visible), affirmations de diagnostic dépliables, placement des indicateurs, règles dataviz complémentaires, contrats d'API requis. |
