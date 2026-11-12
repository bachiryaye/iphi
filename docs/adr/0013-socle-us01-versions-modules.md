# ADR 0013 — Socle US-01 : versions d'outillage, modules `monitor` et `topology`, valeurs locales par défaut

- **Statut :** Proposée
- **Date :** 2026-11-12
- **Portée :** US-01

## Contexte

La réalisation de US-01 impose des choix que le dossier laisse ouverts : version exacte de Python, compatibilité de la chaîne TypeScript, emplacement des tables `platform` et `monitor_heartbeat` dans les modules (rules.md A-01), démarrage « clone propre → `docker compose up` » sans fichier `.env`.

## Décision

- **Python 3.14** (`requires-python >=3.14,<3.15`) : version stable la plus récente bien supportée par FastAPI, SQLAlchemy 2.1, psycopg 3 et mypy ; `uuid.uuid7()` natif pour les identifiants (ADR 0008).
- **TypeScript 5.9 et ESLint 9** : TypeScript 7 (portage natif) n'est pas encore pris en charge par `typescript-eslint` (< 6.1) ni par `openapi-typescript` (^5) ; `eslint-plugin-jsx-a11y` ne prend pas encore en charge ESLint 10. Montée de version dès que ces outils suivent.
- **Modules ajoutés à A-01** : `monitor` (observabilité d'IPHI lui-même : battement du worker, readiness ; architecture §02 « monitor ») et `topology` (plateforme, puis composants et dépendances en US-02). `audit_event` relève d'`identity` (audit des actions sensibles, architecture §02).
- **Image backend unique** construite par le service `migrate` ; `api` et `worker` la réutilisent (`pull_policy: never`) : évite trois constructions concurrentes de la même image (ADR 0001).
- **Mot de passe PostgreSQL local par défaut** (`iphi_local_dev`) dans `compose.yaml`, surchargeable par `.env` : condition du critère « clone propre → `docker compose up` ». Il ne protège qu'une base de démonstration liée à `127.0.0.1` ; ce n'est pas un secret au sens de X-01.
- **Port PostgreSQL publié 5433** (et non 5432) pour coexister avec une instance locale existante ; configurable par `IPHI_DB_PORT`.
- **Readiness** : le battement du worker est jugé périmé après 3 cycles (même tolérance que R-TEL-001) ; `/ready` répond 503 avec le détail des contrôles, jamais 200 en aveugle. Le battement utilise l'heure murale (liveness du processus), pas l'horloge de plateforme (D-13).
- **Frontend servi par Nginx** en Compose, avec proxy même origine vers l'API : pas de politique CORS à ouvrir, CSP sans `unsafe-inline` (script d'initialisation du thème en fichier externe).

## Alternatives écartées

- Python 3.12 : compatible mais sans `uuid7` natif ; 3.15 : trop récent pour l'écosystème typé.
- TypeScript 7 sans lint typé : perte de `strictTypeChecked` et du client OpenAPI généré.
- Exiger `cp .env.example .env` avant le premier démarrage : contredit le critère d'acceptation US-01.
- CORS ouvert sur l'origine Vite : inutile avec un proxy même origine.

## Conséquences

- rules.md A-01 liste `monitor` et `topology`.
- Le passage à TypeScript 7 / ESLint 10 sera une tâche d'outillage dédiée.
- Toute exposition hors poste local exige un mot de passe fourni par `.env` (rappelé dans le README).
