# Backlog de développement

**Epics, user stories, tâches verticales et stratégie de livraison IA**

*IPHI  |  Dossier de conception  |  Version 1.0  |  12 novembre 2026*

## 01 — Politique de découpage

Découpage vertical : une tâche inclut backend, données, frontend et tests lorsque ces éléments participent à un même résultat utilisateur. Ne pas créer de tâche autonome “créer modèle”, “créer endpoint”, “ajouter bouton” si une seule livraison cohérente peut les intégrer.

Une story est indépendante lorsque possible, démontrable en moins de quelques jours avec assistance IA, et comporte des critères d’acceptation observables. Les tâches sont regroupées si elles partagent contexte, dépendances et validation. On sépare seulement en cas de risque, d’attente externe ou de changement d’architecture.

Définition de terminé (DoD) : code intégré, tests exécutés et réussis, interface fonctionnelle si concernée, données reproductibles, documentation minimale, pas de secret, démo vérifiée. L’IA doit fournir commandes et résultats de test, pas seulement déclarer “done”.

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
| E5 — Rapports | US-09 Export et rapport d’incident | P1 | US-05, US-08 |
| E6 — Qualité & livraison | US-10 Démo reproductible et tests e2e | P0 | US-06 |
| E6 — Qualité & livraison | US-11 Sécurité et durcissement | P1 | US-06 |
| E7 — Connectivité | US-12 Adaptateur MQTT ou OPC UA | P2 | US-03 |

P0 = indispensable pour candidature ; P1 = enrichissement utile ; P2 = extension si temps disponible. Priorité absolue : une démo complète, stable et honnête.

## 03 — Stories et tâches de réalisation

### US-01 — En tant que développeur, je démarre IPHI en une commande.

Tâche unique : créer monorepo frontend/backend, Compose PostgreSQL, migrations initiales, configuration d’exemple, checks lint/type/test, CI et README de démarrage.

Acceptation : clone propre → docker compose up → API /health et frontend accessibles ; CI verte ; aucun secret commité.

### US-02 — En tant qu’ingénieur, je simule une infrastructure avec pannes contrôlées.

Tâche unique : modéliser 5–7 composants dépendants, générer métriques/logs, exposer scénarios down/latency/stale/errors et mécanisme reset/seed.

Acceptation : même scénario et même seed produisent des événements reproductibles ; l’état simulé est identifiable.

### US-03 — En tant qu’ingénieur, je consulte des mesures historisées fiables.

Tâche unique : implémenter pipeline de collecte, validation, persistance PostgreSQL, index temporels, API de consultation et tests d’intégration.

Acceptation : séries temporelles consultables et horodatées UTC ; données invalides rejetées ; absence de collecte visible.

### US-04 — En tant qu’ingénieur, je vois l’état de santé calculé de chaque service.

Tâche unique : moteur de règles configurables, fenêtres temporelles, état Unknown, hystérésis, agrégation et endpoints avec justification; tests unitaires paramétrés.

Acceptation : panne, latence et stale data produisent les états attendus; retour normal sans oscillations intempestives.

### US-05 — En tant qu’ingénieur, je reçois un incident unique avec ses preuves.

Tâche unique : ouverture/déduplication/résolution, historique, preuves, API de recherche et accusé de réception; tests des transitions.

Acceptation : une panne persistante ne crée pas d’incidents dupliqués; chaque incident renvoie vers ses observations.

### US-06 — En tant qu’opérateur, je surveille la plateforme sur un tableau de bord.

Tâche unique : vue globale React, composants, statuts, graphiques, liste incidents et branchement API; inclure états chargement/erreur/vide et tests UI essentiels.

Acceptation : déclencher une panne fait apparaître un statut Critical et un incident dans l’interface.

### US-07 — En tant qu’opérateur, j’investigue sans recharger la page.

Tâche unique : SSE, détail composant, graphe des dépendances, historique et filtres incidents; test reconnexion.

Acceptation : changements visibles sans rechargement et interface utilisable si flux SSE temporairement indisponible.

### US-08 — En tant qu’ingénieur, j’obtiens un diagnostic IA traçable.

Tâche unique : service d’analyse déterministe des preuves, adaptateur LLM configurable, schéma JSON strict, citations evidence_ids, UI diagnostic, tests avec faux fournisseur et fallback.

Acceptation : faits séparés des hypothèses; aucune preuve inventée; panne LLM n’empêche pas la supervision.

### US-09 — En tant que responsable, j’exporte un rapport d’incident.

Tâche unique : génération PDF et CSV avec chronologie, preuves, règles et recommandations, endpoint et bouton de téléchargement; tests du contenu.

Acceptation : export fidèle aux observations; diagnostic IA clairement étiqueté.

### US-10 — En tant qu’évaluateur, je reproduis la démonstration.

Tâche unique : parcours e2e automatisé “injecter panne → détecter → ouvrir incident → diagnostiquer”, jeu de données seed, script demo, README et guide vidéo.

Acceptation : démo exécutable sans accès à un vrai système industriel, tests verts sur environnement propre.

### US-11 — En tant qu’administrateur, je contrôle l’accès et les actions.

Tâche unique : auth et RBAC viewer/engineer/admin, journal d’audit, validation des accès aux scénarios et diagnostics, tests négatifs.

Acceptation : viewer ne peut pas injecter de panne; événements sensibles audités; secrets hors dépôt.

### US-12 — En tant qu’intégrateur, je branche une source industrielle standard.

Tâche unique : définir interface connecteur, implémenter un seul protocole MQTT ou OPC UA avec serveur simulé, tests d’intégration et documentation.

Acceptation : mêmes règles et dashboard fonctionnent avec le connecteur sans modifier le moteur métier.

## 04 — Ordonnancement optimisé pour assistants IA

Lot 1 (US-01 + US-02) : socle et simulateur; lancer dans une seule session de codage si le contexte tient, mais valider le démarrage avant la simulation.

Lot 2 (US-03 + US-04) : ingestion et moteur de santé; tâches distinctes car les règles nécessitent un contrat d’observations stable.

Lot 3 (US-05 + US-06) : incident et interface; livrer une première démonstration complète. Ce jalon prime sur les ajouts.

Lot 4 (US-08 + US-09) : diagnostic et rapport; mutualiser le modèle de preuves. US-07 peut être traité en parallèle si API stabilisée.

Lot 5 (US-10 + US-11) : robustesse et dossier portfolio. US-12 uniquement après validation des jalons P0.

Règle anti-fragmentation : une tâche = une intention fonctionnelle + un jeu de tests. Ne pas ouvrir de sous-tâches de 10 minutes. Scinder seulement si la réalisation ne peut pas être revue et validée de manière fiable dans une seule livraison.

## 05 — Format standard de mission pour l’assistant IA

Contexte : citer l’epic, la story et les contrats existants. Objectif : une seule capacité démontrable. Périmètre : composants à modifier, interfaces à respecter. Contraintes : sécurité, typage, tests, documentation. Livrable : code fonctionnel et commandes de validation. Critères d’acceptation : reprendre ceux de la story.

Instruction de contrôle : avant de coder, résumer les fichiers à modifier et les décisions structurantes; ensuite implémenter de bout en bout; exécuter les tests; fournir les résultats et limites; ne pas marquer terminé si la démo ou les tests échouent.

Les assistants IA ne doivent pas inventer des APIs AVEVA PI, ni annoncer une compatibilité non testée. Tout nouveau connecteur doit être clairement identifié comme simulation ou intégration vérifiée.

## 06 — Risques et arbitrages

| Risque | Réponse prévue |
|---|---|
| Sur-ingénierie | P0 d’abord, P1 ensuite; microservices exclus |
| Hallucination IA | Schémas stricts, preuves, fallback et tests négatifs |
| Complexité OT | Sources simulées; connecteur réel seulement avec autorisation |
| Intégration cassée | CI et e2e à chaque jalon |
| Délais candidature | Démo US-01 à US-06 et US-10 prioritaire |
| Dette documentaire | README, ADR succinctes, OpenAPI générée |

---
*Pied de page du document source : IPHI — Document de travail | Architecture et livraison incrémentale*
