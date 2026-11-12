# Architecture Decision Records

Format : contexte, décision, alternatives, conséquences. Statut de toutes les ADR ci-dessous : **Acceptée — 2026-11-12** (0001–0012 : revue v1.1 du dossier ; 0013 : socle US-01 ; 0014 : simulateur US-02).

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

Nouvelle ADR : copier le format, numéro suivant, statut *Proposée* jusqu'à validation.
