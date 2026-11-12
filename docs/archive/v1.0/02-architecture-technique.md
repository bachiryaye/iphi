# Architecture technique détaillée

**Industrial Platform Health Intelligence — décisions, composants, données, API, sécurité et jalons**

*IPHI  |  Dossier de conception  |  Version 1.0  |  12 novembre 2026*

## 01 — Décisions structurantes

Architecture retenue : monolithe modulaire FastAPI, frontend React/TypeScript séparé, PostgreSQL, simulateur et connecteurs interchangeables. Un seul dépôt Git et un environnement Docker Compose reproductible.

Pourquoi : simplifier le développement, les tests et la démonstration tout en préservant des frontières explicites. Pas de microservices distribués pour la V1.

| Décision | Choix | Justification |
|---|---|---|
| Backend | Python 3.12+ / FastAPI | API typée, validation Pydantic |
| Frontend | React / TypeScript / Vite | Interface moderne, composants testables |
| Données | PostgreSQL / Alembic | Historique relationnel et migrations |
| Jobs | Scheduler interne et workers simples | Suffisant en prototype; interface extensible |
| Temps réel | SSE (ou WebSocket si nécessaire) | Flux serveur vers dashboard |
| IA | Adaptateur LLM + schéma JSON validé | Fournisseur interchangeable et garde-fous |
| Packaging | Docker Compose / GitHub Actions | Reproductibilité et CI |

## 02 — Vue des composants

Flux principal : simulateur / adaptateurs → ingestion → stockage des observations → évaluation des règles → incidents → diagnostic contextualisé → API → interface. Les métriques et événements sont horodatés en UTC.

- simulation : génère métriques, logs, états et scénarios de défaillance reproductibles avec graine configurable.
- ingestion : reçoit, normalise, valide, déduplique et stocke les observations.
- health : calcule les états Healthy, Warning, Critical, Unknown, avec règles versionnées et hystérésis.
- incidents : regroupe les alertes, maintient un cycle de vie, conserve les preuves.
- diagnostics : corrèle les événements et interroge facultativement le LLM.
- reporting : produit synthèses CSV/PDF et exports des preuves.
- identity : authentification, rôles et audit des actions sensibles.
- connectors : contrats de collecte pour simulation, REST, puis MQTT/OPC UA.

## 03 — Modèle de données logique

| Entité | Champs essentiels / relations |
|---|---|
| platform | id, name, environment, created_at |
| component | id, platform_id, type, criticality, status, config |
| dependency | source_component_id, target_component_id, kind |
| metric_sample | id, component_id, metric_name, value, unit, observed_at, source |
| log_event | id, component_id, severity, message, observed_at, fingerprint |
| health_rule | id, metric_name, operator, threshold, severity, window, enabled, version |
| rule_evaluation | id, rule_id, component_id, status, evidence, evaluated_at |
| incident | id, component_id, status, severity, opened_at, resolved_at, fingerprint |
| incident_evidence | incident_id, observation_type, observation_id |
| diagnostic | id, incident_id, model, facts, hypotheses, recommendations, confidence_label |
| audit_event | id, actor_id, action, target, occurred_at |

Toutes les entités doivent avoir des migrations et contraintes d’intégrité. Ne pas mettre les données simulées et réelles dans un même environnement sans étiquetage explicite.

## 04 — Contrats API et événements

| Route indicative | Comportement |
|---|---|
| GET /api/v1/platforms | Liste des plateformes et états agrégés |
| GET /api/v1/components/{id} | Détails, dépendances et métriques |
| GET /api/v1/metrics | Séries filtrées par composant/période |
| GET /api/v1/incidents | Recherche, filtre et pagination |
| POST /api/v1/incidents/{id}/ack | Accusé de réception audité |
| POST /api/v1/incidents/{id}/diagnose | Diagnostic IA sur preuves persistées |
| POST /api/v1/simulations/scenarios | Déclenchement d’un scénario autorisé |
| GET /api/v1/events/stream | SSE des changements d’état |
| GET /api/v1/reports/incidents/{id} | Export PDF |

Conventions : OpenAPI auto-générée, modèles Pydantic, pagination, erreurs structurées, idempotence des opérations sensibles, dates ISO-8601 UTC, correlation_id dans les logs.

## 05 — Moteur de santé et incidents

Une règle évalue une métrique sur une fenêtre et produit une observation explicable. Unknown signifie absence de preuve récente; ne doit pas être interprété comme Healthy. Les alertes utilisent une fenêtre ou hystérésis pour éviter les oscillations.

Agrégation : un composant critique en état Critical rend l’état global Critical selon une politique explicite. Les incidents sont regroupés par fingerprint et composant pour éviter les doublons. Cycle : Open → Acknowledged → Resolved (avec réouverture documentée).

Cas de test obligatoires : service down, latence croissante, stale data malgré service up, surcharge simulée, incident répété, retour à la normale, absence de métriques.

## 06 — IA, sûreté et traçabilité

Le LLM ne reçoit que des preuves structurées sélectionnées : métriques, événements, règles et dépendances. Sortie JSON validée : observed_facts[], hypotheses[], recommended_checks[], uncertainty, evidence_ids[]. Le moteur déterministe demeure autorité pour l’état de santé.

- Interdire les affirmations causales certaines sans preuve et les commandes correctives automatiques.
- Prévoir timeout, budget de tokens, masquage des secrets, refus des instructions présentes dans les logs, audit du prompt et de la réponse.
- En cas d’indisponibilité IA : dashboard, règles et incidents restent opérationnels.
- Les recommandations doivent être liées à des evidence_ids existants; signaler explicitement les limites.

## 07 — Sécurité, qualité et exploitation

- RBAC minimal : viewer, engineer, admin. Scénarios de simulation réservés à engineer/admin.
- Secrets exclusivement via variables d’environnement; jamais dans Git. Authentification et limitation des accès.
- Tests : unitaires pour règles; intégration pour API/DB; parcours e2e pour scénario panne → incident → dashboard; tests de non-régression.
- CI : lint, typage, tests backend/frontend, migrations, build conteneurs. Données de démonstration anonymes et reproductibles.
- Observabilité du moniteur lui-même : logs structurés, erreurs de collecte, métriques de scheduler et statut du fournisseur IA.
- Pas de connexion à une infrastructure OT réelle sans autorisation, segmentation et validation de cybersécurité.

## 08 — Jalons et conditions de livraison

| Jalon | Résultat observable | Critère de sortie |
|---|---|---|
| J0 | Repository + Docker + migration + CI | Démarrage documenté sur machine propre |
| J1 | Simulation et ingestion | Mesures et logs persistés |
| J2 | Règles et incidents | Panne détectée et preuves consultables |
| J3 | Dashboard temps réel | Démo bout en bout stable |
| J4 | Diagnostic IA et rapport | Hypothèses sourcées, fallback IA |
| J5 | Qualité et connecteur optionnel | Tests verts, documentation, vidéo |

Ordre strict : obtenir J3 démontrable avant d’ajouter des connecteurs avancés ou une sophistication IA. Toute fonctionnalité non testée est “en cours”, pas “terminée”.

---
*Pied de page du document source : IPHI — Document de travail | Architecture et livraison incrémentale*
