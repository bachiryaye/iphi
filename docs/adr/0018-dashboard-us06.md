# ADR 0018 — Dashboard US-06 : métrique clé côté serveur, garde de mutation exposée, rafraîchissement, graphiques et composants d'interface

- **Statut :** Acceptée
- **Date :** 2026-11-13
- **Portée :** US-06 (précise l'ADR 0009 et le design system §6, §7, §9, §11 ; complète l'architecture §04.1)

## Contexte

Le design system décrit six écrans et deux contrats additifs (`key_metric` pour le `RangeMeter`, `state-history` pour le `StateBand`). Il ne précise pas : quelle valeur porte la métrique clé (échantillon brut ou agrégat de la règle), ce qu'elle devient sans échantillon, comment l'interface sait qu'une mutation sera refusée, comment calculer une fenêtre d'historique en temps de plateforme, ni quelles primitives d'interface adopter avant que des dialogues ou menus soient nécessaires.

## Décision

- **`key_metric` (API 0.6.0, additif).** Choisie par le serveur (`health/domain/key_metric.py`, pur) : la règle mesurée à l'origine du pire état du composant (`reason`), sinon la règle de la métrique par défaut du type (§6.1). Une règle d'absence ne mesure rien et passe la main au défaut. La **valeur est la dernière mesure de la règle** (agrégat sur sa fenêtre, p. ex. p95 sur 60 s), comparable à ses seuils ; elle est datée `evaluated_at` (fin de fenêtre) et non `observed_at`, pour ne pas faire passer un agrégat pour une observation. Sans échantillon dans la fenêtre, l'objet reste présent avec `value = null` (l'interface affiche « no data » avec la règle et la fenêtre) ; `key_metric = null` seulement avant la première évaluation. `kind` : `meter` (plus haut = pire), `availability` (`up` : texte « DOWN since », jamais une jauge), `value` (plus bas = pire hors sonde : nombre seul). Bornes : minimum du catalogue de métriques ; maximum 1,25 × le seuil le plus haut, plafonné au maximum du catalogue. `state` est l'état de la règle, Unknown une fois périmé (D-02) : l'interface ne dessine alors aucun pointeur et n'écrit jamais « DOWN » ni « Answering probes » sur une mesure périmée ; « DOWN since » n'apparaît qu'une fois l'état Warning ou Critical confirmé par l'anti-rebond. Quand le pire état vient de R-TEL-001 (absence), le repli sur la métrique par défaut est cohérent : cette règle ne se déclenche que si aucune observation n'existe, donc la règle de repli est elle aussi sans échantillon.
- **Garde de mutation exposée.** `GET /system/status` renvoie `mutations {enabled, reason}` (politique ADR 0007). L'interface masque les contrôles de scénarios et d'horloge, et désactive Acknowledge, Resolve et Diagnose, en affichant la raison ; le serveur reste l'autorité (refus audités).
- **Rafraîchissement.** Toutes les vues interrogent l'API toutes les 10 s (TanStack Query) jusqu'au SSE de US-07 ; chaque carte affiche « Updated N s ago » (horloge du poste, puisque c'est l'âge de la réponse) puis, si un rafraîchissement échoue avec des données à l'écran, l'état périmé du §8 (heure et âge des données, nouvelle tentative). Après une mutation réussie, tous les caches sont invalidés. Les fenêtres d'historique et les âges des instants stockés (« 4 min ago », « for 2 min ») sont calculés en temps de plateforme, estimé entre deux lectures de `system/status` (mode, vitesse, `platform_time`) ; un seul minuteur partagé fait avancer tous les âges affichés.
- **Graphiques.** ECharts 6 importé module par module et chargé à la demande (bloc séparé, ~520 ko, hors du bundle initial de ~490 ko), rendu SVG, axe en UTC. Une métrique par graphique, une série en `--accent` ; trous rendus comme des trous ; seuils en pointillés étiquetés avec leur base (« R-LAT-001: p95 over 60 s ») car la règle juge un agrégat, pas l'échantillon tracé ; en mode agrégé, plage min–max ombrée sous la moyenne. Nom accessible = résumé textuel (dernière valeur, min, max, seuils, trous) et bouton « View as table ».
- **Primitives d'interface.** Pas de shadcn/Radix en US-06 : `<select>` natif pour les filtres, formulaires et confirmations en ligne (Resolve, Reset) au lieu de dialogues, infobulle maison au survol et au focus. Radix sera introduit avec le premier composant qui exige un piège de focus (dialogue, menu). Écart au §11 assumé.
- **Topologie simple.** Disposition fixe calculée dans l'interface depuis les arêtes (colonne = plus long chemin `data_flow` depuis une source ; un composant relié seulement en `runtime` se place sous son premier dépendant) ; arête « impact » quand le dépendant est impacté par la dépendance ou par la même cause qu'elle (`impacted_by` du serveur). Aucune règle de santé côté client. Tableau équivalent sous le graphe.
- **Incident.** Les 200 premières preuves et les premiers événements de `GET /incidents/{id}` sont affichés, avec mention quand il en reste. Les occurrences consécutives sont regroupées dans la chronologie. Les puces de preuve surlignent la ligne de la chaîne et le point du graphique (mode brut).
- **Logs.** Regroupés par empreinte côté interface sur les 100 derniers logs ≥ warning de l'heure écoulée.
- **E2E.** Playwright 1.63 (`pnpm test:e2e`) contre la stack Compose : reset, `collector_down`, tuile Critical, un incident listé, page incident. Branchement en CI avec US-10.

## Alternatives écartées

- Valeur brute du dernier échantillon dans `key_metric` : position incohérente avec les seuils, qui jugent un p95 ou une somme.
- `key_metric = null` sans échantillon : l'interface perdrait le nom de la métrique et la règle à citer.
- Tenter la mutation et lire le refus : l'opérateur découvre l'interdiction après coup.
- Dialogues modaux natifs (`confirm`) : interdits par le design system ; Radix ajouté pour deux confirmations seulement : dépendance sans besoin de piège de focus.
- React Flow dès US-06 : prévu en US-07 avec l'interaction.

## Conséquences

- Les six écrans fonctionnent sur les données réelles du simulateur, sans règle de santé dans l'interface.
- Le `StateBand` attend `state-history` (US-07) ; la page Component montre la métrique, les règles et les logs.
- Charge : environ une requête par carte toutes les 10 s et par onglet ouvert ; acceptable en local, remplacée par le SSE en US-07.
- **Reporté à US-07** (contrats additifs) : fenêtre relative résolue par le serveur (`last_seconds`) au lieu de l'estimation de l'horloge de plateforme côté client ; arêtes « impact » calculées par le serveur ; `health` des dépendances dans `DependencyOut` ; total d'incidents actifs ; logs regroupés par empreinte en SQL (le regroupement porte aujourd'hui sur les 100 derniers logs) ; filtres de la liste Components passés à l'API.
