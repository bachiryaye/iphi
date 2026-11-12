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
- `Makefile` (ou `justfile`) : `make up`, `make test`, `make lint`, `make check`, `make demo` (stub documenté comme tel jusqu'à US-10).
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
| US-02 | Fait (2026-11-12), CI à confirmer au prochain push | Test golden seed 42 + `collector_down` + 120 ticks : empreinte identique sur deux exécutions, ordre quelconque, après persistance et redémarrage (PostgreSQL) et via le CLI hors base ; chaque observation porte `source=simulation` et `scenario_run_id` ; 9 scénarios testés ; stack Compose propre (`down -v`) → seed 7 composants / 6 dépendances / baseline, API de simulation via Nginx ; 164 tests backend, couverture 95 % |
| US-03 … US-12 | À faire | — |

Le statut n'est mis à jour que sur preuve (commandes et résultats).

---
*Pied de page du document source : IPHI — Document de travail | Backlog et livraison incrémentale (v1.0 indiquait par erreur « Architecture et livraison incrémentale »)*
