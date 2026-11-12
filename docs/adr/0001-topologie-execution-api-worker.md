# ADR 0001 — Topologie d'exécution : monolithe modulaire, processus api et worker, SSE via LISTEN/NOTIFY

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Le scheduler (collecte, évaluation, incidents) doit s'exécuter exactement une fois par cycle. Placé dans le processus FastAPI, il serait dupliqué par chaque worker uvicorn et couplerait la latence HTTP aux traitements. Le temps réel doit atteindre le navigateur sans broker supplémentaire.

## Décision

- Un seul code et une seule image Docker, deux points d'entrée : `api` (HTTP + SSE) et `worker` (boucle `run_cycle`).
- Le worker prend un *advisory lock* PostgreSQL : une seule instance active ; une seconde instance attend.
- Le worker publie `NOTIFY iphi_events` ; l'API écoute (`LISTEN`, connexion psycopg asynchrone dédiée) et relaie aux clients SSE.
- SQLAlchemy 2 en mode synchrone pour le domaine ; seule l'écoute SSE est asynchrone.

## Alternatives écartées

- Scheduler dans l'API (APScheduler) : risque d'exécutions multiples, couplage.
- Celery/Redis ou RabbitMQ : infrastructure lourde injustifiée pour 7 composants.
- WebSockets : bidirectionnel inutile ; SSE suffit et se reconnecte nativement.
- Microservices séparés : exclus par le dossier (sur-ingénierie).

## Conséquences

- Compose comporte `api` et `worker` ; `/ready` vérifie le battement du worker.
- Les tests d'intégration appellent `run_cycle` directement, sans scheduler.
- Passer à plusieurs plateformes à fort volume demanderait de revoir le verrou unique (hors V1).
