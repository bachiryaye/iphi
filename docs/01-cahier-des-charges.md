# INDUSTRIAL PLATFORM HEALTH INTELLIGENCE

*IPHI  |  Cahier des charges fonctionnel et technique*

VERSION 1.1  •  12 NOVEMBRE 2026

> **Statut :** exigences de référence. La v1.0 d'origine est conservée dans
> `docs/archive/v1.0/01-cahier-des-charges.md` (et en DOCX/PDF à la racine). Les ajouts v1.1 sont
> signalés *« Précision v1.1 »* ; aucune exigence v1.0 n'a été supprimée.

| Version | Date | Changements |
|---|---|---|
| 1.0 | 2026-11-12 | Version initiale. |
| 1.1 | 2026-11-12 | Périmètre V1 explicite (inclus / exclu), objectifs de performance chiffrés, scénarios de validation complétés, exigences de design (§14), correspondance avec le backlog. |

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

*Précision v1.1 — périmètre V1.* **Inclus :** objectifs 1 à 6 sur une plateforme simulée de 7 composants ; un connecteur MQTT simulé (objectif 7, optionnel P2). **Exclus de la V1 :** recherche d'incidents similaires (M4), assistant IA conversationnel (M5, vue « questions »), connecteurs REST / OPC UA / Prometheus, AVEVA PI, toute infrastructure réelle, détection statistique et maintenance prédictive. Détail et justification : backlog §02.1.

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
- *Précision v1.1 :* écrans, sémantique visuelle des états et règles d'accessibilité définis dans `docs/04-design-system.md` (§14). La « vue IA » V1 présente les diagnostics structurés et leurs preuves ; les questions libres sont hors V1. Actualisation par SSE (US-07) ; la démo P0 utilise un rafraîchissement périodique.

### M6 — Incidents et reporting

- Historique, accusé de réception, commentaires, changements d’état et piste d’audit.
- Exports CSV et rapports PDF ; distinction entre mesures, règles et analyse IA.
- *Précision v1.1 :* les commentaires sont des événements de la chronologie de l'incident (US-07) ; accusé de réception, résolution et réouverture suivent le cycle de vie de l'architecture §05.5.

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
- *Précision v1.1 :* modèle détaillé (champs, contraintes, rétention) dans l'architecture §03.1. Correspondances : Metrics → `metric_sample` (avec `quality`), Logs → `log_event`, ComponentDependencies → `dependency`, IncidentEvents → `incident_event`, DiagnosticReports → `diagnostic`, Users → `app_user`.

## 7. Exigences non fonctionnelles

- Fiabilité : panne d’un collecteur isolée ; échecs visibles et historisés.
- Sécurité : authentification, rôles, validation d’entrées, secrets hors dépôt, journalisation sensible.
- Traçabilité : chaque diagnostic référence métriques, événements et règles.
- Performance : collecte configurable ; objectifs chiffrés définis et vérifiés par charge.
  *Précision v1.1 :* cycle de collecte 5 s ; détection d'un arrêt ≤ 15 s ; affichage d'un changement < 2 s (SSE) ; API p95 < 300 ms ; dashboard < 2 s au premier affichage ; 7 jours de rétention. Valeurs et méthode de mesure : architecture §07.2, vérification en US-10.
- *Précision v1.1 —* Observabilité du moniteur : IPHI affiche en permanence son propre état (collecte, retard du worker, fournisseur IA) et ne présente jamais un état « Healthy » faute de données (`Unknown`).
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
| *v1.1* — Service répond mais données procédé figées | Alerte de fraîcheur distincte, aucun incident de disponibilité |
| *v1.1* — Perte de connexion intermittente | Un seul incident de connectivité, pas d'oscillation d'état |
| *v1.1* — Saturation CPU/mémoire simulée | Warning puis Critical aux seuils configurés |
| *v1.1* — File d'attente croissante | Alerte de backlog aux seuils configurés |
| *v1.1* — Erreurs répétées | Un seul incident mis à jour, pas de tempête d'incidents |
| *v1.1* — Plus aucune observation | État Unknown (jamais Healthy) et incident de perte de télémétrie |
| *v1.1* — Retour à la normale | Résolution automatique après période de stabilité |
| *v1.1* — Utilisateur viewer tente d'injecter une panne | Refus serveur et audit (à partir de US-11) |

Catalogue détaillé (cibles, signaux, états et incidents attendus) : architecture §05.6.

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

*Précision v1.1 :* l'ordonnancement de référence est celui du backlog (US-01 → US-06 + US-10 pour la démo P0). Les phases ci-dessus restent une lecture fonctionnelle ; correspondance dans l'architecture §08.1.

La candidature ne dépend pas de la réalisation des cinq phases. Priorité : une version verticale fonctionnelle, testée et démontrable ; les extensions seront poursuivies après l’envoi du dossier.

## 11. Critères d’acceptation du prototype

- Lancer l’ensemble du prototype localement avec des données de démonstration.
- Superviser simultanément plusieurs composants et injecter des pannes.
- Historiser métriques et événements, créer automatiquement des incidents.
- Visualiser les preuves et expliquer les diagnostics sans inventer de causes.
- Continuer la surveillance lorsque le fournisseur IA est indisponible.
- Exécuter les tests de validation depuis une procédure documentée.

## 12. Évolutions possibles

Supervision de systèmes réels, recherche d'incidents similaires, assistant IA conversationnel, connecteurs multi-protocoles, séries temporelles avancées, détection statistique, maintenance prédictive, corrélation IT/OT, jumeaux numériques et intégration à Industrial Engineering Studio. Ces pistes ne font pas partie des critères d’acceptation du prototype initial.

## 13. Gouvernance du développement

- Toute fonctionnalité doit être rattachée à une exigence et à un test.
- Tout code est relu et exécuté avant d'être intégré.
- Aucune fonctionnalité n’est déclarée terminée sans démonstration et tests.
- Documenter les compromis, les limitations et les composants simulés.
- Conserver des commits cohérents et une procédure d’installation reproductible.

## 14. Design et expérience utilisateur (ajout v1.1)

- L'interface est un instrument d'ingénierie inspiré des principes d'IHM haute performance : la couleur signale l'anormal, l'état normal reste discret.
- Un état n'est jamais porté par la couleur seule (forme d'icône + texte + couleur) ; `Unknown` a un traitement visuel propre.
- Chaque état, incident et diagnostic affiché donne accès à ses preuves (règle, évaluation, observations).
- Les données simulées sont signalées en permanence ; le temps est affiché en UTC et en heure locale.
- Thèmes clair et sombre, contraste WCAG 2.2 AA vérifié, navigation complète au clavier.
- Spécification normative : `docs/04-design-system.md`.

Principe directeur : un outil d’ingénierie crédible, explicable et vérifiable, dans lequel l’IA renforce l’analyse sans remplacer les contrôles déterministes.

---
*Pied de page du document source : IPHI  •  Cahier des charges v1.0  •  Projet personnel*
