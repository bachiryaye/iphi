# Backlog de développement

**Epics, user stories, tâches verticales et stratégie de livraison**

*IPHI  |  Dossier de conception  |  Version 1.1  |  12 novembre 2026*

> **Statut :** backlog de référence (il prime sur les phases du cahier des charges et les jalons de
> l'architecture pour l'ordonnancement). La v1.0 d'origine est conservée dans
> `docs/archive/v1.0/03-backlog.md`.

## Historique des versions

| Version | Date | Changements |
|---|---|---|
| 1.0 | 2026-11-12 | Version initiale. |
| 1.1 | 2026-11-12 | Mêmes 8 epics et 12 stories (IDs et dépendances conservés). Critères d'acceptation rendus vérifiables ; diagnostic **déterministe** déplacé dans US-05 (résout la dépendance cachée de US-10 envers US-08) ; garde de sécurité P0 avant US-11 ; 7 scénarios de panne + télémétrie perdue ; design system intégré à US-01/US-06 ; commentaires d'incident dans US-07 ; objectifs de performance et dossier portfolio dans US-10 ; choix MQTT pour US-12 ; périmètre exclu explicite. |

## 01 — Politique de découpage

Découpage vertical : une tâche inclut backend, données, frontend et tests lorsque ces éléments participent à un même résultat utilisateur. Ne pas créer de tâche autonome “créer modèle”, “créer endpoint”, “ajouter bouton” si une seule livraison cohérente peut les intégrer.

Une story est indépendante lorsque possible, démontrable en moins de quelques jours, et comporte des critères d'acceptation observables. Les tâches sont regroupées si elles partagent contexte, dépendances et validation. On sépare seulement en cas de risque, d'attente externe ou de changement d'architecture.

Définition de terminé (DoD) : code intégré, tests exécutés et réussis, interface fonctionnelle si concernée, données reproductibles, documentation minimale, pas de secret, démo vérifiée. Toute livraison fournit commandes et résultats de test, pas seulement une déclaration « terminé ».

*Ajout v1.1 — DoD interface :* toute story touchant l'interface respecte `docs/04-design-system.md` (composants de statut communs, états vide/chargement/erreur/dégradé, contraste AA, navigation clavier, aucune couleur seule pour porter une sévérité) et passe les tests axe sans violation sérieuse.

### 01.1 — Scénarios obligatoires

Toute livraison préserve ces scénarios ; US-10 les couvre en e2e :

1. Collecteur arrêté → `Critical` (selon la règle) → **un** incident ouvert avec preuves.
2. Dégradation de latence → `Warning`/`Critical` selon les seuils, puis retour stable.
3. Données périmées alors que le service répond → problème de fraîcheur détecté distinctement.
4. Aucune observation récente → `Unknown`, jamais faussement `Healthy`.
5. Signaux d'erreur répétés → pas de tempête d'incidents dupliqués.
6. LLM indisponible → supervision, incidents et dashboard restent fonctionnels.
7. Un viewer tente de modifier un scénario → refusé et audité (exigible à partir de US-11 ; avant, garde `IPHI_DEV_MUTATIONS` + écoute locale, ADR 0007).
8. Environnement propre et seedé → comportement de démonstration identique.

## 02 — Backlog priorisé par livraisons

| Epic | Story / livrable | Priorité | Dépend de |
|---|---|---|---|
| E0 — Fondations | US-01 Socle exécutable et CI | P0 | — |
| E1 — Simulation & collecte | US-02 Infrastructure simulée et scénarios | P0 | US-01 |
| E1 — Simulation & collecte | US-03 Ingestion et historique | P0 | US-02 |
| E2 — Santé & incidents | US-04 Règles et états de santé | P0 | US-03 |
| E2 — Santé & incidents | US-05 Incidents avec preuves | P0 | US-04 |
| E3 — Expérience opérateur | US-06 Dashboard opérationnel | P0 | US-05 |
| E3 — Expérience opérateur | US-07 Investigation et temps réel | P1 | US-06 |
| E4 — Diagnostic IA | US-08 Diagnostic structuré et fallback | P1 | US-05 |
| E5 — Rapports | US-09 Export et rapport d'incident | P1 | US-05, US-08 |
| E6 — Qualité & livraison | US-10 Démo reproductible et tests e2e | P0 | US-06 |
| E6 — Qualité & livraison | US-11 Sécurité et durcissement | P1 | US-06 |
| E7 — Connectivité | US-12 Adaptateur MQTT ou OPC UA | P2 | US-03 |

P0 = indispensable pour candidature ; P1 = enrichissement utile ; P2 = extension si temps disponible. Priorité absolue : une démo complète, stable et honnête.

*Précision v1.1 :* la démonstration P0 (US-01 → US-06 + US-10) inclut un diagnostic **déterministe** (US-05) ; le diagnostic LLM (US-08) l'enrichit sans en être une condition. US-12 retient **MQTT** (ADR 0011).

### 02.1 — Hors périmètre V1 (décision explicite)

| Exigence du cahier des charges | Décision |
|---|---|
| M4 — recherche d'incidents similaires | Hors V1 (piste d'évolution). |
| M5 — vue IA conversationnelle (questions libres) | Hors V1 ; US-08 fournit un diagnostic structuré à la demande. |
| M2/M7 — connecteurs REST, OPC UA, Prometheus | Hors V1 ; seul MQTT (US-12, P2) est implémenté. Interface connecteur prête. |
| AVEVA PI System, infrastructure OT réelle | Hors V1, sans exception. |
| Multi-plateformes actives, multi-tenant, haute disponibilité, Kubernetes | Hors V1 (le modèle supporte plusieurs plateformes ; une seule est seedée). |
| Détection statistique / ML, maintenance prédictive | Hors V1 (CDC §12). |

## 03 — Stories et tâches de réalisation

Chaque story conserve sa tâche unique et son acceptation v1.0 ; les compléments v1.1 précisent le périmètre et les preuves attendues.

### US-01 — En tant que développeur, je démarre IPHI en une commande.

Tâche unique : créer monorepo frontend/backend, Compose PostgreSQL, migrations initiales, configuration d'exemple, checks lint/type/test, CI et README de démarrage.

Acceptation : clone propre → docker compose up → API /health et frontend accessibles ; CI verte ; aucun secret commité.

*Compléments v1.1 :*
- Dépôt git initialisé, structure monorepo de l'architecture (§02) ; services Compose `db`, `migrate`, `api`, `worker` (boucle vide avec battement), `frontend` ; ports liés à `127.0.0.1`.
- Backend : `uv` + lockfile, FastAPI, réglages typés, logs JSON avec `correlation_id`, erreurs RFC 9457, `/health` et `/ready`, migration initiale (`platform`, `monitor_heartbeat`, `audit_event`), Ruff, mypy strict, pytest.
- Frontend : `pnpm` + lockfile, Vite + React + TS strict, Tailwind + **tokens du design system** (thèmes clair/sombre), polices IBM Plex auto-hébergées, **coque applicative** (barre latérale, barre supérieure, bannière « SIMULATED DATA », horloge UTC/locale), page d'accueil affichant l'état de `/ready` avec états chargement/erreur ; client API généré depuis l'OpenAPI ; ESLint, Vitest.
- `Makefile` (ou `justfile`) : `make up`, `make test`, `make lint`, `make check`, `make demo` (stub documenté comme tel jusqu'à US-10, livré par US-10).
- CI GitHub Actions : lint, typage, tests back/front, `alembic upgrade head` sur PostgreSQL éphémère, vérification de dérive du client API, build des images, gitleaks.
- `.env.example` sans secret ; README (objectif, avertissement simulation, prérequis, démarrage, tests).
- **Preuve de sortie :** sur clone propre, `docker compose up --build` → `/health` 200, `/ready` 200 après migration, frontend affiche « API ready » ; `make check` vert ; CI verte.

### US-02 — En tant qu'ingénieur, je simule une infrastructure avec pannes contrôlées.

Tâche unique : modéliser 5–7 composants dépendants, générer métriques/logs, exposer scénarios down/latency/stale/errors et mécanisme reset/seed.

Acceptation : même scénario et même seed produisent des événements reproductibles ; l'état simulé est identifiable.

*Compléments v1.1 :*
- Les 7 composants et dépendances de l'architecture §05.6 (seed idempotent) ; tables `component`, `dependency`, `sim_clock`, `scenario_run`.
- Horloge de plateforme (`realtime`/`accelerated`/`manual`) et générateur pur à compteur (ADR 0002).
- **Scénarios :** `baseline`, `collector_down`, `latency_rise`, `stale_data`, `intermittent_loss`, `error_burst`, `resource_pressure`, `backlog_growth`, `telemetry_blackout` — chacun avec résultat attendu documenté.
- API : catalogue, démarrage, arrêt, liste des runs, reset, horloge (garde `IPHI_DEV_MUTATIONS`, ADR 0007).
- **Preuves :** test « golden » : seed 42 + scénario + 120 ticks ⇒ empreinte (hash) identique des observations générées sur deux exécutions et après redémarrage ; chaque observation porte `source=simulation` et `scenario_run_id`.

### US-03 — En tant qu'ingénieur, je consulte des mesures historisées fiables.

Tâche unique : implémenter pipeline de collecte, validation, persistance PostgreSQL, index temporels, API de consultation et tests d'intégration.

Acceptation : séries temporelles consultables et horodatées UTC ; données invalides rejetées ; absence de collecte visible.

*Compléments v1.1 :*
- Interface `Connector`, `run_cycle` (étapes 1–3 et 7–8), `collection_run`, `metric_definition`, `metric_sample` (avec `quality`, `received_at`), `log_event`.
- Validation : métrique/unité inconnue, hors plage, futur > 30 s, tardif > 10 min ⇒ rejet compté ; doublon ⇒ ignoré et compté.
- **Isolation :** l'échec d'un connecteur est enregistré (`collection_run.status=failed`) sans interrompre les autres ni le cycle.
- API `metrics/catalog`, `metrics` (sous-échantillonnage `max_points`, trous conservés), `logs`, `system/status`.
- Job de rétention (7 jours, preuves d'incident protégées).
- **Preuves :** tests d'intégration sur PostgreSQL réel pour chaque cas de rejet, doublon, observation tardive, connecteur en échec, et requête bornée (`max_points`).

### US-04 — En tant qu'ingénieur, je vois l'état de santé calculé de chaque service.

Tâche unique : moteur de règles configurables, fenêtres temporelles, état Unknown, hystérésis, agrégation et endpoints avec justification; tests unitaires paramétrés.

Acceptation : panne, latence et stale data produisent les états attendus; retour normal sans oscillations intempestives.

*Compléments v1.1 :*
- `config/health_rules.yaml` (règles §05.3), `health_rule` versionnée et immuable, `rule_state`, `rule_evaluation`, `component_health`, `platform_health`.
- Sondes actives et distinction `Critical` / `Unknown` ; fraîcheur de télémétrie vs fraîcheur métier (ADR 0003).
- Agrégation par criticité et annotation d'impact (ADR 0004).
- API `platforms`, `topology`, `components`, `components/{id}/health`, `health-rules`, `rule-evaluations`, toutes avec justification (règle/version, fenêtre, seuil, valeur, IDs de preuves).
- **Preuves :** tests paramétrés par scénario du catalogue (état attendu par composant et pour la plateforme) ; test de propriété (Hypothesis) : un signal oscillant autour d'un seuil dans la bande d'hystérésis ne provoque aucun changement d'état ; `telemetry_blackout` ⇒ `Unknown`, jamais `Healthy`.

### US-05 — En tant qu'ingénieur, je reçois un incident unique avec ses preuves.

Tâche unique : ouverture/déduplication/résolution, historique, preuves, API de recherche et accusé de réception; tests des transitions.

Acceptation : une panne persistante ne crée pas d'incidents dupliqués; chaque incident renvoie vers ses observations.

*Compléments v1.1 :*
- `incident` (index unique partiel sur l'empreinte), `incident_evidence` (FK réelles), `incident_event`, `incident_impact` ; cycle de vie complet de l'ADR 0005 : aggravation, résolution automatique, résolution manuelle (409 si condition active), réouverture sous 15 min, suppression en aval.
- **Diagnostic déterministe** (architecture §05.7) au schéma de l'architecture §06.1, persisté dans `diagnostic` (`kind=deterministic`) ; `POST /diagnose?mode=deterministic`, `GET /diagnostics`.
- API `incidents` (curseur, filtres), `incidents/{id}`, `ack` (idempotent), `resolve` ; `audit_event` pour chaque action humaine.
- **Preuves :** `collector_down` ⇒ exactement **1** incident actif, aval rattaché en impact ; `error_burst` 10 min ⇒ 1 incident, `occurrence_count` > 1 ; `latency_rise` ⇒ `severity_changed` puis `auto_recovered` ; réouverture < 15 min vs nouvel incident > 15 min ; double incident concurrent impossible (test d'insertion concurrente contre l'index).

### US-06 — En tant qu'opérateur, je surveille la plateforme sur un tableau de bord.

Tâche unique : vue globale React, composants, statuts, graphiques, liste incidents et branchement API; inclure états chargement/erreur/vide et tests UI essentiels.

Acceptation : déclencher une panne fait apparaître un statut Critical et un incident dans l'interface.

*Compléments v1.1 (écrans selon `docs/04-design-system.md`) :*
- **Overview** : état plateforme + justification, tuiles composants (état, impact, dernière observation), incidents actifs, santé du moniteur.
- **Topology (version simple)** : chaîne de dépendances en disposition fixe, états et impact ; le graphe interactif vient en US-07.
- **Component** : métriques avec unités, seuils et bandes, trous visibles, évaluations de règles avec justification, logs récents.
- **Incidents** : liste filtrable ; **Incident** : résumé, chronologie, chaîne de preuves, diagnostic déterministe, ack/resolve.
- **Scenarios** : catalogue avec résultat attendu, démarrage/arrêt, horloge (visible seulement si les mutations sont autorisées).
- Rafraîchissement périodique (10 s) avec indicateur « updated Xs ago » ; état « données périmées » si l'API ne répond plus.
- **Preuves :** tests Vitest des composants de statut et des états vide/chargement/erreur ; test axe sur chaque écran ; test e2e minimal `collector_down` ⇒ tuile `Critical` + incident listé.

### US-07 — En tant qu'opérateur, j'investigue sans recharger la page.

Tâche unique : SSE, détail composant, graphe des dépendances, historique et filtres incidents; test reconnexion.

Acceptation : changements visibles sans rechargement et interface utilisable si flux SSE temporairement indisponible.

*Compléments v1.1 :*
- SSE via `LISTEN/NOTIFY` (événements de l'architecture §04.3), invalidation des caches, repli en rafraîchissement 30 s signalé à l'écran.
- Graphe interactif des dépendances (React Flow, disposition hiérarchique), propagation d'impact visible, sélection ⇒ panneau composant.
- **Commentaires d'incident** (CDC M6), filtres persistés dans l'URL, chronologie superposée aux métriques (repères d'incident sur les graphiques).
- Annonce accessible (`aria-live="polite"`) des nouveaux incidents.
- **Preuves :** e2e : démarrer un scénario ⇒ tuile mise à jour < 2 s sans rechargement ; couper le flux ⇒ bandeau « Live updates paused » et repli fonctionnel ; reconnexion ⇒ état resynchronisé.

### US-08 — En tant qu'ingénieur, j'obtiens un diagnostic IA traçable.

Tâche unique : service d'analyse déterministe des preuves, adaptateur LLM configurable, schéma JSON strict, citations evidence_ids, UI diagnostic, tests avec faux fournisseur et fallback.

Acceptation : faits séparés des hypothèses; aucune preuve inventée; panne LLM n'empêche pas la supervision.

*Compléments v1.1 :*
- Le service déterministe existe depuis US-05 ; US-08 ajoute l'adaptateur (`none` / `fake` / fournisseur configuré), le pipeline de l'architecture §06.2, la limitation de débit et l'UI.
- UI : faits, hypothèses (avec niveau d'incertitude) et vérifications visuellement distincts ; chaque affirmation porte des **puces de citation** cliquables vers la preuve ; étiquette permanente « AI-generated — verify against evidence » ; comparaison avec le diagnostic déterministe.
- **Preuves :** tests avec faux fournisseur : preuve inventée ⇒ retirée et signalée ; JSON invalide ⇒ `rejected` + fallback ; timeout ⇒ fallback ; log contenant une injection de prompt ⇒ consigne non suivie ; fournisseur coupé ⇒ dashboard et incidents intacts.

### US-09 — En tant que responsable, j'exporte un rapport d'incident.

Tâche unique : génération PDF et CSV avec chronologie, preuves, règles et recommandations, endpoint et bouton de téléchargement; tests du contenu.

Acceptation : export fidèle aux observations; diagnostic IA clairement étiqueté.

*Compléments v1.1 :*
- `GET /reports/incidents/{id}?format=pdf|csv` ; PDF généré depuis un modèle HTML/CSS aux couleurs du design system (WeasyPrint, ADR 0012) : en-tête « SIMULATED ENVIRONMENT », résumé, chronologie, preuves, règles/versions, diagnostics (déterministe et IA séparés et étiquetés), horodatages UTC.
- CSV : une ligne par preuve/événement, cellules neutralisées contre l'injection de formules.
- **Preuves :** tests du contenu (textes et IDs présents, aucune donnée absente de la base), test d'injection CSV, test d'échappement HTML.

### US-10 — En tant qu'évaluateur, je reproduis la démonstration.

Tâche unique : parcours e2e automatisé “injecter panne → détecter → ouvrir incident → diagnostiquer”, jeu de données seed, script demo, README et guide vidéo.

Acceptation : démo exécutable sans accès à un vrai système industriel, tests verts sur environnement propre.

*Compléments v1.1 :*
- « Diagnostiquer » = diagnostic **déterministe** (US-05) ; le diagnostic LLM est ajouté au parcours quand US-08 est livré, avec le faux fournisseur en CI.
- `make demo` : environnement propre, seed fixe, horloge `accelerated`, enchaînement scénarisé ; `docs/demo.md` avec commandes et résultats attendus observables.
- E2E Playwright couvrant les scénarios obligatoires 1 à 6 et 8 (§01.1).
- Test de performance léger vérifiant les objectifs de l'architecture §07.2 (résultats publiés, pas inventés).
- **Dossier portfolio :** README avec captures réelles (thèmes clair et sombre), schéma d'architecture, `docs/case-study.md` (problème, décisions, compromis, limites), script de vidéo de 3 minutes.

### US-11 — En tant qu'administrateur, je contrôle l'accès et les actions.

Tâche unique : auth et RBAC viewer/engineer/admin, journal d'audit, validation des accès aux scénarios et diagnostics, tests négatifs.

Acceptation : viewer ne peut pas injecter de panne; événements sensibles audités; secrets hors dépôt.

*Compléments v1.1 :*
- Sessions serveur, Argon2id, CSRF, en-têtes de sécurité, rôles appliqués côté serveur (ADR 0007) ; `IPHI_DEV_MUTATIONS` retiré du chemin nominal.
- Écrans : connexion, menu utilisateur avec rôle, actions masquées **et** refusées côté serveur, journal d'audit (admin).
- **Preuves :** matrice de tests négatifs rôle × route de mutation (403 + `audit_event.outcome=denied`) ; scénario obligatoire 7 ; `pip-audit`/`pnpm audit`/gitleaks en CI.

### US-12 — En tant qu'intégrateur, je branche une source industrielle standard.

Tâche unique : définir interface connecteur, implémenter un seul protocole MQTT ou OPC UA avec serveur simulé, tests d'intégration et documentation.

Acceptation : mêmes règles et dashboard fonctionnent avec le connecteur sans modifier le moteur métier.

*Compléments v1.1 :*
- Protocole retenu : **MQTT** (Mosquitto en profil Compose `mqtt`, publieur simulé, schéma de topic et de payload JSON documenté et validé). OPC UA reste une évolution.
- Données étiquetées `source=mqtt` et toujours `environment=simulation` (le publieur est simulé).
- **Preuves :** test d'intégration avec broker réel en conteneur ; un scénario `collector_down` reproduit via MQTT produit le même état et le même incident ; aucune modification de `health/` ni `incidents/`.

## 04 — Ordonnancement des livraisons

Lot 1 (US-01 + US-02) : socle et simulateur; lancer dans une seule session de codage si le contexte tient, mais valider le démarrage avant la simulation.

Lot 2 (US-03 + US-04) : ingestion et moteur de santé; tâches distinctes car les règles nécessitent un contrat d'observations stable.

Lot 3 (US-05 + US-06) : incident et interface; livrer une première démonstration complète. Ce jalon prime sur les ajouts.

Lot 4 (US-08 + US-09) : diagnostic et rapport; mutualiser le modèle de preuves. US-07 peut être traité en parallèle si API stabilisée.

Lot 5 (US-10 + US-11) : robustesse et dossier portfolio. US-12 uniquement après validation des jalons P0.

Règle anti-fragmentation : une tâche = une intention fonctionnelle + un jeu de tests. Ne pas ouvrir de sous-tâches de 10 minutes. Scinder seulement si la réalisation ne peut pas être revue et validée de manière fiable dans une seule livraison.

*Précision v1.1 :* US-10 étant P0, sa partie « démo P0 » (parcours e2e avec diagnostic déterministe, `make demo`, README) est livrée **juste après le lot 3** ; le dossier portfolio final (captures, vidéo, case study) est complété au lot 5.

## 05 — Format standard d'une tâche de réalisation

Contexte : citer l'epic, la story et les contrats existants. Objectif : une seule capacité démontrable. Périmètre : composants à modifier, interfaces à respecter. Contraintes : sécurité, typage, tests, documentation. Livrable : code fonctionnel et commandes de validation. Critères d'acceptation : reprendre ceux de la story.

Instruction de contrôle : avant de coder, résumer les fichiers à modifier et les décisions structurantes; ensuite implémenter de bout en bout; exécuter les tests; fournir les résultats et limites; ne pas marquer terminé si la démo ou les tests échouent.

Aucune réalisation n'invente d'API AVEVA PI ni n'annonce une compatibilité non testée. Tout nouveau connecteur doit être clairement identifié comme simulation ou intégration vérifiée.

## 06 — Risques et arbitrages

| Risque | Réponse prévue |
|---|---|
| Sur-ingénierie | P0 d'abord, P1 ensuite; microservices exclus |
| Hallucination IA | Schémas stricts, preuves, fallback et tests négatifs |
| Complexité OT | Sources simulées; connecteur réel seulement avec autorisation |
| Intégration cassée | CI et e2e à chaque jalon |
| Délais candidature | Démo US-01 à US-06 et US-10 prioritaire |
| Dette documentaire | README, ADR succinctes, OpenAPI générée |
| *v1.1* — Tests non déterministes (horloge, scheduler) | Horloge `manual` + `run_cycle` appelable directement ; générateur pur |
| *v1.1* — Tempête d'incidents en cascade | Suppression en aval + index unique partiel |
| *v1.1* — Moniteur « vert » en aveugle | Sondes actives, `Unknown`, incident `telemetry_loss`, statut du moniteur affiché |
| *v1.1* — Interface générique peu crédible | Design system dédié inspiré ISA-101, revue visuelle à US-01 et US-06 |
| *v1.1* — Démo exposée sans authentification avant US-11 | Garde `IPHI_DEV_MUTATIONS` + écoute locale uniquement |

## 07 — Suivi d'avancement

| Story | Statut | Preuve |
|---|---|---|
| US-01 | Fait (2026-11-12) | `docker compose up --build` → `/health` 200, `/ready` 200 ; CI GitHub Actions verte (backend + PostgreSQL, frontend, contrat API, images, secrets) |
| US-02 | Fait (2026-11-12), CI verte sur `main` (run 43730564222) | Test golden seed 42 + `collector_down` + 120 ticks : empreinte identique sur deux exécutions, ordre quelconque, après persistance et redémarrage (PostgreSQL) et via le CLI hors base ; chaque observation porte `source=simulation` et `scenario_run_id` ; 9 scénarios testés ; stack Compose propre (`down -v`) → seed 7 composants / 6 dépendances / baseline, API de simulation via Nginx ; 164 tests backend, couverture 95 % |
| US-03 | Fait (2026-11-12), CI verte sur `main` (run 43730564222) | Tests d'intégration sur PostgreSQL réel pour chaque code de rejet, doublon (échantillons et logs), observation tardive dans et hors tolérance, connecteur en échec, sortie invalide et échec d'insertion isolés par connecteur, reset sans rejeu des runs arrêtés, rétention par lots, requête bornée (`max_points`, fenêtre ≤ 7 j, trous explicites) ; Compose : migration 0002 → 0003 sur volume existant et démarrage propre, `system/status` `ok` puis `stalled` worker arrêté ; cycle temps réel 35–77 ms, `GET /metrics` 2 000 points p95 163 ms ; 290 tests backend, couverture 96 % |
| US-04 | Fait (2026-11-13), CI verte sur `main` (run 43730564222) | Test d'intégration par scénario du catalogue (8 pannes + baseline) sur PostgreSQL réel : séquence d'états attendue de la règle visée (ex. `latency_rise` : Healthy → Warning → Critical), état du composant et de la plateforme, puis retour stable à Healthy sans remontée de sévérité ; `collector_down` Critical en ≤ 15 s (9 s mesurées en temps réel sur la stack) et aval impacté ; `telemetry_blackout` ⇒ `Unknown`, jamais `Healthy` ; tests de propriété (Hypothesis) : signal oscillant dans la bande d'hystérésis sans changement d'état, aucune montée sur des dépassements plus courts que `raise_after`, plateforme jamais plus douce qu'une panne d'un composant high/medium ; même historique d'états sur deux bases propres en cadence 5 s et 60 s ; API santé (justification règle/version, fenêtre, seuil, valeur, preuves ; état périmé ⇒ `unknown`) ; cycle temps réel p95 123 ms ; 414 tests backend, couverture 97 % |
| US-05 | Fait (2026-11-13), CI verte sur `main` (run 43730564222) | Test d'intégration par scénario du catalogue (8 pannes) sur PostgreSQL réel : un seul incident actif de la classe attendue, puis résolution automatique au retour ; `collector_down` ⇒ un incident `availability`, historian et analytics rattachés en impact (`downstream_suppressed`), connectivité absorbée ou reclassée ; `error_burst` 10 min ⇒ 1 incident, `occurrence_count` > 5 ; `latency_rise` ⇒ `opened` → `severity_changed` → `resolved` (`auto_recovered`) ; réouverture sous 15 min, nouvel incident au-delà ; insertion concurrente d'une même empreinte refusée par l'index unique partiel ; reset (incidents `reset`, preuves et observations citées conservées, historique repartant après le reset) ; rétention des preuves ; append-only ; API (filtres, curseurs, `ack` idempotent audité, `resolve` 409 tant que la condition est active, diagnostic déterministe 201/200 idempotent, mutations refusées et auditées) ; propriété Hypothesis : jamais plus d'un incident par panne dans la fenêtre ; Compose : migration 0004 → 0005 sur volume existant, `collector_down` détecté en ≤ 10 s, résolu automatiquement ~5 min après l'arrêt, aucun incident parasite 5 min 30 s après un reset ; cycle temps réel médiane ≈ 115 ms, p95 ≈ 190 ms ; 479 tests backend, couverture 97 % |
| US-06 | Fait (2026-11-14), CI verte sur `main` (run 43730564222) | Six écrans (Overview, Topology, Components/Component, Incidents/Incident, Scenarios, Rules) sur données réelles du simulateur, revus à 1440 × 900 et 768 px, thèmes clair et sombre ; API 0.6.0 : `key_metric` choisi par le serveur (règle au pire état, sinon métrique par défaut du type) et `system/status.mutations` (ADR 0018) ; rafraîchissement 10 s avec « Updated N s ago » et vue périmée ; états chargement/vide/erreur/périmé/permission testés ; Vitest : 70 tests dont axe sans violation sérieuse sur chaque écran ; 490 tests backend, couverture 97 % ; e2e Playwright contre Compose (Nginx) : reset, `collector_down` ⇒ ligne collector-01 Critical et un seul incident listé, page incident avec R-AVAIL-001 (23,4 s sur les images finales) |
| US-10 | Fait (2026-11-16), CI verte sur `main` (run 44127899156) | `make demo` sur pile propre (projet `iphi-demo`, volume neuf) : six actes verts en 125 s ; `make test-e2e` juste après : 8/8 en une exécution (scénarios obligatoires 1 à 6 et 8, premier affichage 332–1 061 ms) ; captures README régénérées depuis la pile (clair et sombre) ; `make perf` : détection `collector_down` ≤ 14,9 s, `GET /incidents` et `GET /metrics` brut p95 < 100 ms, cycle p95 288 ms (0,2 jour) et 388 ms (7 jours, 2ᵉ exécution) ; `GET /metrics` 7 jours agrégé p95 337 et 613 ms : **objectif de 300 ms non atteint** sur le poste de mesure (disque rotatif, hôte chargé ; 123 ms en base à chaud), publié tel quel dans `docs/performance.md` ; images exécutables sans Compose (ADR 0020) ; dossier : `docs/demo.md`, `docs/case-study.md`, `docs/video-script.md`, ADR 0019 |
| US-08 | Fait (2026-11-18), PR #8 fusionnée, CI verte sur `main` (run 44243405370) | Adaptateurs none/fake/openai, sortie stricte/citations/masquage, comparaison et fallback persistés, quota PostgreSQL, worker non bloqué pendant le réseau ; migration 0007 montée/descente et parité ORM ; 373 tests unitaires backend, 18 intégration API/migrations + 48 régressions API/readiness, 75 tests frontend dont axe, 12 tests UI ciblés finaux ; démo PASS (113 s), e2e P0 8/8 en une exécution (5,1 min, affichage 525–723 ms) et parcours fake US-08 1/1 (23,5 s) ; revue visuelle 1440/768 clair/sombre, ADR 0021. Première exécution e2e : performance échouée sous saturation disque, conservée dans le journal puis suite complète rejouée verte sans seuil modifié. CI PR 44200231369 : 558 tests backend (96 %), 75 frontend, démo 115 s, P0 8/8 et fake 1/1 ; six jobs verts sur PR puis sur main. Fournisseur payant NOT VERIFIED. Extension OpenRouter demandée le 18 novembre : adaptateur gratuit uniquement, plafond de prix zéro, contrôle du coût déclaré et identité de modèle transport ; ADR 0024. Validation locale : 437 tests unitaires, 13 intégrations PostgreSQL, lint/typage/imports verts ; appel réel particle/free réussi (5 faits retenus, 608 tokens de sortie, 4444 ms), comparaison persistée, supervision HTTP 200. Extension fusionnée par PR #11 (9906bed) ; CI PR 44308305743 verte 6/6 : 638 backend (96 %), 89 frontend, navigateur 11 PASS + fake 1 PASS ; CI main 44310969804 verte 6/6 sur 9906bed. |
| US-09 | Fait (2026-11-18), PR #9 fusionnée, CI verte sur `main` (run 44248348754) | PDF/CSV sur instantané PostgreSQL cohérent, registre complet borné sans troncature silencieuse, diagnostics séparés et repli, ressources limitées aux polices embarquées ; ADR 0022. 393 tests unitaires backend, 9 intégrations rapports (texte PDF/IDs/versions, fake et repli, injections CSV/HTML, bornes, garde de rendu/CSV disponible) et 32 régressions incidents/diagnostics/migrations verts ; 78 tests frontend et 15 tests UI finaux ciblés, lint/typage et audit strict verts. Démo 122 s ; téléchargement PDF/CSV e2e 1/1 en 43,3 s, parcours fake US-08 1/1 ; revue PDF de 26 pages et UI clair/sombre 1440/768, téléchargement clavier vérifié. Premier e2e exportait avant confirmation availability : attente corrigée selon ADR 0017, contenu de règle exigé inchangé. Suite locale finale 9 PASS / un parcours fake optionnel ignoré (fake validé séparément) ; CI PR 44247106592 : 587 backend (96 %), 78 frontend, démo 110 s, navigateur 9 PASS + fake 1 PASS, six jobs verts puis CI main verte. |
| US-07 | Fait (2026-11-18), PR #10 fusionnée, CI verte sur `main` (run 44305090793) | ADR 0023 ; SSE natif / LISTEN-NOTIFY transactionnel, resynchronisation et repli 30 s ; React Flow/dagre, sélection URL/clavier et panneau ; historique serveur avec lacunes Unknown, reset, versions/preuves et pics critiques conservés, réticule partagé, repères incidents/scénarios ; commentaires audités et chronologie paginée. Backend complet 610 PASS (96 %), puis historique final 9 PASS et intégration étendue 2 PASS ; frontend 89 PASS ; lint/typage/imports et audit dépendances verts. Démo propre 121 s. Navigateur ciblé : délai après changement validé 620 ms, repli réel 30 s, resynchronisation 975 ms (55 s) ; graphe clavier/historique/commentaire persistant PASS (44,2 s). Arrêt API avec flux ouvert : 2,91 s, code 0, nettoyage lifespan. Échecs locaux et corrections conservés dans le journal ; Régression globale 11 PASS / un parcours fake optionnel ignoré (6,9 min), fake 1 PASS séparément (19,6 s), filtre URL/rechargement final PASS (32,2 s) ; captures réelles 1440 clair/768 sombre revues. CI PR 44302943906 : 611 backend (96 %), 89 frontend, démo 110 s, navigateur 11 PASS + fake 1 PASS ; affichage 185–284 ms, changement validé 497 ms, reconnexion 263 ms ; six jobs verts sur PR puis main. |
| US-11 | Validé (2026-11-19), PR #12 | ADR 0025, migration 0008 montée/descente/parité ORM ; sessions hachées, Argon2id, expiration/révocation, CSRF, matrice rôle × mutation, audit admin borné, connexion/menu/permissions. CI PR 44483207714 verte 6/6 : 663 tests backend (96 %), 102 frontend, démo propre 109 s, navigateur 12 PASS et fake 1 PASS ; affichage 237–272 ms, SSE 381 ms/reconnexion 240 ms. Local : démo authentifiée 126 s, 42 régressions API/identité et 25 contrôles identité/bootstrap/SSE verts, viewer/admin navigateur 1 PASS (24,6 s), captures réelles clair/sombre régénérées et revues. Deux suites navigateur locales sous forte charge disque : 9 PASS/3 FAIL puis 7 PASS/5 FAIL ; seuil premier affichage non atteint (2 486/2 052 ms), délais PDF/worker et attente de redirection consignés dans docs/performance.md, aucune assertion de performance assouplie. Audits des dépendances et scan de secrets verts. |
| US-12 | Validé (2026-11-19), PR #14 | ADR 0026 ; profil Compose MQTT isolé, Mosquitto réel et publieur synthétique, paho-mqtt2.2, lots JSON versionnés/bornés, qualité/horloge/scénario conservés, transport unique et reset avec preuves conservées ; aucun changement dans health/ ni incidents/. CI 44538711480 verte 6/6 : 692 tests backend (95 %, dont quatre intégrations broker/PostgreSQL), 102 frontend, démo standard 110 s, navigateur 12 PASS + fake 1 PASS ; démo MQTT 114 s et navigateur MQTT 1 PASS (24,4 s). Contrat MQTT final local 27 PASS. Création/nettoyage Docker locaux sous pression disque et conflit du port 5435 consignés dans docs/performance.md ; ports MQTT configurables, services du propriétaire préservés. |

Le statut n'est mis à jour que sur preuve (commandes et résultats).

---
*Pied de page du document source : IPHI — Document de travail | Backlog et livraison incrémentale (v1.0 indiquait par erreur « Architecture et livraison incrémentale »)*
