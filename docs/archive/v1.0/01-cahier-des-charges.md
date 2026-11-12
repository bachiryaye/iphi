# INDUSTRIAL PLATFORM HEALTH INTELLIGENCE

*IPHI  |  Cahier des charges fonctionnel et technique*

VERSION 1.0  •  12 NOVEMBRE 2026

Projet personnel d’ingénierie — Observabilité IT/OT, données industrielles, diagnostic et IA

Finalité immédiate : prototype démontrable pour une candidature en Industrial Data & AI. Vision : plateforme évolutive et réutilisable pour des projets de jumeau numérique.

## 1. Contexte et justification

Les infrastructures industrielles reposent sur des chaînes d’acquisition, de communication, d’historisation et d’exploitation des données. Une panne de collecteur, une latence excessive, des données obsolètes, des erreurs applicatives ou la saturation d’un service peuvent dégrader la visibilité sur le procédé.

IPHI centralise les observations techniques, évalue la santé des composants et aide l’ingénieur à investiguer les incidents. Le prototype fonctionnera sans licence AVEVA PI System ; toute compatibilité future sera fondée sur des interfaces documentées et autorisées.

## 2. Objectifs et périmètre

1. Superviser plusieurs composants et services d’une plateforme de données industrielles.
2. Collecter, historiser et visualiser métriques, journaux et événements.
3. Détecter des anomalies à l’aide de règles déterministes configurables.
4. Corréler les incidents et produire des hypothèses explicables.
5. Assister l’investigation par IA, avec preuves et incertitudes explicites.
6. Simuler des pannes reproductibles et produire des rapports techniques.
7. Prévoir des connecteurs futurs pour les environnements industriels réels.

## 3. Utilisateurs cibles

| Profil | Usage principal |
|---|---|
| Ingénieur OT / automatisme | Surveillance des flux et des communications |
| Ingénieur Industrial Data | Qualité et disponibilité des données |
| Administrateur système | Services, ressources, logs et disponibilité |
| Responsable technique | Indicateurs consolidés et rapports |

## 4. Exigences fonctionnelles

### M1 — Simulateur d’infrastructure

- Composants : source PLC/capteur simulée, passerelle, collecteur, historisation, base de données, API et analyse.
- Injection de pannes : arrêt, latence, perte intermittente, données obsolètes, saturation simulée, erreurs répétées et files d’attente.
- Chaque composant expose un état, des métriques horodatées et un journal d’événements. Les données fictives sont signalées.

### M2 — Acquisition et monitoring

- Collecte périodique configurable, contrôles de disponibilité, latence, erreurs, ressources et fraîcheur des données.
- Historisation des métriques et distinction entre Healthy, Warning, Critical et Unknown.
- Détection d’interruptions de collecte ; adaptateurs extensibles REST, OPC UA, MQTT et Prometheus.

### M3 — Évaluation déterministe de santé

- Règles configurables : identifiant, cible, métrique, seuil, sévérité, justification et recommandation.
- Évaluation des erreurs, de la latence, de la fraîcheur, de la saturation et des interruptions.
- Agrégation pondérée par criticité, sans masquer un incident majeur derrière une moyenne.

### M4 — Diagnostic et assistant IA

- Corrélation temporelle, dépendances entre services, recherche d’incidents similaires et causes probables.
- Synthèse IA des événements, recommandations d’investigation et explications contextualisées.
- Séparation obligatoire entre faits observés, hypothèses et conseils ; aucune correction automatique sur systèmes réels.

### M5 — Dashboard d’observabilité

- Vue générale : état global, services, incidents, dernière collecte et disponibilité.
- Vue infrastructure : graphe de dépendances et états ; vue composant : métriques, logs et diagnostics.
- Vue incidents : gravité, chronologie, investigation ; vue IA : questions et preuves associées.
- Interface responsive, accessible et actualisée par SSE ou WebSocket.

### M6 — Incidents et reporting

- Historique, accusé de réception, commentaires, changements d’état et piste d’audit.
- Exports CSV et rapports PDF ; distinction entre mesures, règles et analyse IA.

### M7 — Intégration et extensibilité

- Architecture de connecteurs avec interfaces stables et gestion des erreurs.
- Connecteurs futurs : REST, MQTT, OPC UA, Prometheus ; AVEVA PI uniquement après vérification des interfaces et droits.

## 5. Architecture technique

| Couche | Choix proposé | Responsabilité |
|---|---|---|
| Frontend | React, TypeScript, Vite | Interface, graphiques, cartographie |
| Backend | Python, FastAPI | API, collecte, orchestration |
| Stockage | PostgreSQL | Métriques, logs, incidents, audit |
| IA | Couche multi-fournisseurs | Synthèses et diagnostic assisté |
| Exécution | Docker Compose | Environnement reproductible |
| Qualité | Pytest, tests frontend, GitHub Actions | Tests et intégration continue |

Architecture recommandée : monolithe modulaire. Séparer acquisition, diagnostic, règles, incidents, IA et interface via des contrats explicites ; éviter les microservices prématurés.

## 6. Modèle de données minimal

- Platforms, Components, ComponentDependencies.
- Metrics (timestamp, unité, valeur, source, qualité), Logs, HealthRules.
- Incidents, IncidentEvents, DiagnosticReports, Users et AuditEvents.
- Index temporels et clés de relation ; migrations versionnées.

## 7. Exigences non fonctionnelles

- Fiabilité : panne d’un collecteur isolée ; échecs visibles et historisés.
- Sécurité : authentification, rôles, validation d’entrées, secrets hors dépôt, journalisation sensible.
- Traçabilité : chaque diagnostic référence métriques, événements et règles.
- Performance : collecte configurable ; objectifs chiffrés définis et vérifiés par charge.
- Maintenabilité : typage, documentation API, tests, conventions et versionnage.
- IA : schémas de sortie validés, erreurs gérées, fonctionnement déterministe maintenu si le LLM est indisponible.

## 8. Scénarios de validation

| Scénario | Résultat attendu |
|---|---|
| Arrêt d’un collecteur | Incident et impact sur dépendances |
| Latence croissante | Alertes aux seuils configurés |
| Données obsolètes | Alerte distincte d’une panne de service |
| Événements corrélés | Synthèse IA avec faits / hypothèses |
| LLM indisponible | Monitoring et règles toujours opérationnels |
| Traçabilité | Preuves consultables depuis l’incident |

## 9. Livrables

1. Application web fonctionnelle et backend documenté.
2. Simulateur, stockage, moteur de règles et diagnostic IA.
3. Dashboard, incidents et génération de rapports.
4. Tests automatisés, jeux de données et scénarios reproductibles.
5. Docker Compose, CI, documentation d’architecture et API.
6. Dépôt GitHub, vidéo de démonstration et fiche projet portfolio.

## 10. Plan de développement incrémental

| Phase | Résultat démontrable |
|---|---|
| A — Socle | Simulateur, collecte, PostgreSQL, règles, dashboard |
| B — Intelligence | Corrélation, diagnostic IA et preuves |
| C — Supervision | Dépendances, incidents, reporting et UX |
| D — Connectivité | MQTT/OPC UA et tests d’intégration |
| E — Industrialisation | Sécurité, CI/CD, charge et documentation |

La candidature ne dépend pas de la réalisation des cinq phases. Priorité : une version verticale fonctionnelle, testée et démontrable ; les extensions seront poursuivies après l’envoi du dossier.

## 11. Critères d’acceptation du prototype

- Lancer l’ensemble du prototype localement avec des données de démonstration.
- Superviser simultanément plusieurs composants et injecter des pannes.
- Historiser métriques et événements, créer automatiquement des incidents.
- Visualiser les preuves et expliquer les diagnostics sans inventer de causes.
- Continuer la surveillance lorsque le fournisseur IA est indisponible.
- Exécuter les tests de validation depuis une procédure documentée.

## 12. Évolutions possibles

Supervision de systèmes réels, connecteurs multi-protocoles, séries temporelles avancées, détection statistique, maintenance prédictive, corrélation IT/OT, jumeaux numériques et intégration à Industrial Engineering Studio. Ces pistes ne font pas partie des critères d’acceptation du prototype initial.

## 13. Gouvernance du développement assisté par IA

- Toute fonctionnalité doit être rattachée à une exigence et à un test.
- Les assistants IA peuvent produire du code, mais les résultats sont relus et exécutés.
- Aucune fonctionnalité n’est déclarée terminée sans démonstration et tests.
- Documenter les compromis, les limitations et les composants simulés.
- Conserver des commits cohérents et une procédure d’installation reproductible.

Principe directeur : un outil d’ingénierie crédible, explicable et vérifiable, dans lequel l’IA renforce l’analyse sans remplacer les contrôles déterministes.

---
*Pied de page du document source : IPHI  •  Cahier des charges v1.0  •  Projet personnel*
