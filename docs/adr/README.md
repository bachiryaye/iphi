# Architecture Decision Records

Format : contexte, décision, alternatives, conséquences. Statut de toutes les ADR ci-dessous : **Acceptée** — 2026-11-12 (0001–0012 : revue v1.1 du dossier ; 0013 : socle US-01 ; 0014 : simulateur US-02 ; 0015 : ingestion US-03), 2026-11-13 (0016 : moteur de santé US-04 ; 0017 : incidents US-05).

| N° | Décision |
|---|---|
| [0001](0001-topologie-execution-api-worker.md) | Topologie d'exécution : monolithe modulaire, processus api et worker, SSE via LISTEN/NOTIFY |
| [0002](0002-horloge-plateforme-simulation-deterministe.md) | Horloge de plateforme et simulation déterministe |
| [0003](0003-modele-observation-sondes-fraicheur.md) | Modèle d'observation : sondes actives, deux fraîcheurs, qualité, heure de réception |
| [0004](0004-evaluation-sante-agregation-impact.md) | Évaluation de santé, agrégation par criticité et annotation d'impact |
| [0005](0005-cycle-vie-deduplication-incidents.md) | Cycle de vie, déduplication et anti-tempête des incidents |
| [0006](0006-contrat-diagnostic-adaptateur-llm.md) | Contrat de diagnostic, diagnostic déterministe et adaptateur LLM |
| [0007](0007-securite-avant-apres-us11.md) | Sécurité avant et après US-11 |
| [0008](0008-stockage-postgresql-retention.md) | Stockage : PostgreSQL standard, identifiants, rétention et sous-échantillonnage |
| [0009](0009-frontend-design-system.md) | Pile frontend et design system |
| [0010](0010-outillage-langue.md) | Outillage de développement et langue |
| [0011](0011-connecteur-mqtt.md) | US-12 : MQTT plutôt qu'OPC UA |
| [0012](0012-generation-pdf.md) | Génération des rapports PDF |
| [0013](0013-socle-us01-versions-modules.md) | Socle US-01 : versions d'outillage, modules `monitor` et `topology`, valeurs locales par défaut |
| [0014](0014-simulateur-us02.md) | Simulateur US-02 : échantillonnage, empreinte, runs, horloge monotone, garde de mutation |
| [0015](0015-ingestion-us03.md) | Ingestion US-03 : cycle en une transaction, curseur de collecte, dédoublonnage, trous explicites |
| [0016](0016-moteur-sante-us04.md) | Moteur de santé US-04 : évaluation par créneau, hystérésis avec Unknown, versions de règles, lecture périmée |
| [0017](0017-incidents-us05.md) | Incidents US-05 : déclenchement, famille disponibilité/connectivité, occurrences, preuves conservées, diagnostic déterministe |
| [0018](0018-dashboard-us06.md) | Dashboard US-06 : métrique clé côté serveur, garde de mutation exposée, rafraîchissement, graphiques, primitives d'interface |
| [0019](0019-demo-e2e-performance-us10.md) | Démonstration US-10 : environnement propre isolé, démo exécutable, e2e en temps de plateforme, mesure de performance |
| [0020](0020-images-sans-compose.md) | Images exécutables sans Compose : entrypoint par rôle, migration au démarrage, healthchecks |
| [0021](0021-diagnostic-llm-us08.md) | US-08 : diagnostic LLM borné, quota persistant, comparaison déterministe et repli |
| [0022](0022-rapports-incidents-us09.md) | US-09 : rapports PDF/CSV sur instantané cohérent, bornes et rendu sans ressources externes |
| [0023](0023-investigation-stream-history.md) | US-07 : SSE transactionnel, historique prouvé et investigation interactive |
| [0024](0024-openrouter-free-us08.md) | US-08: free-only OpenRouter adapter, zero price ceiling and deterministic fallback |
| [0025](0025-identity-sessions-us11.md) | US-11: server sessions, CSRF, role enforcement and audited access |
| [0026](0026-mqtt-simulation-transport.md) | US-12: bounded MQTT simulation batches, real broker, transport selection and reset |

Nouvelle ADR : copier le format, numéro suivant, statut *Proposée* jusqu'à validation.

- [0027 — Bilingual presentation and beginner help](0027-bilingual-help.md)
- [0028 — Compact hosting with separate API and worker](0028-compact-hosting.md)
