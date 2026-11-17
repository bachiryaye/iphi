# ADR 0020 — Images exécutables sans Compose : entrypoint par rôle, migration au démarrage, healthchecks

- **Statut :** Acceptée (demande du propriétaire)
- **Date :** 2026-11-16
- **Portée :** images backend et frontend (complète l'ADR 0001)

## Contexte

Les images ne fonctionnaient que sous Compose : le rôle (API, worker, migration) était fixé par `command:`, l'ordre de démarrage par `depends_on`, le healthcheck de l'image ne valait que pour l'API, et Nginx visait `api:8000` via le DNS interne de Docker (`127.0.0.11`). Le propriétaire veut pouvoir lancer les conteneurs par leur `ENTRYPOINT`, hors Compose (orchestrateur ou `docker run`).

## Décision

- **Backend : `ENTRYPOINT ["iphi-entrypoint"]`, `CMD ["api"]`.** Rôles : `api` (uvicorn, port `IPHI_PORT`), `worker`, `migrate` (schéma puis seed idempotent), `healthcheck` ; toute autre commande est exécutée telle quelle (`python -m scripts.demo`). Le script fait `exec` : le processus reçoit `SIGTERM` directement.
- **Migration.** Recommandé : un conteneur `migrate` exécuté avant le déploiement (tâche ponctuelle, conteneur d'initialisation). Possible : `IPHI_MIGRATE_ON_START=true` sur `api` ou `worker`. Dans les deux cas le bootstrap prend un verrou consultatif PostgreSQL : des conteneurs démarrés ensemble migrent l'un après l'autre. Il attend la base jusqu'à `IPHI_DB_WAIT_S` (60 s), puisque plus rien n'ordonne les démarrages.
- **Healthcheck par rôle**, dans l'image (`iphi-entrypoint healthcheck`). Le worker touche `IPHI_LIVENESS_FILE` (`/tmp`) après chaque cycle réussi, et pendant l'attente du verrou du planificateur. Si ce fichier existe, il doit avoir moins de `IPHI_LIVENESS_MAX_AGE_S` (300 s). Sinon, le conteneur doit répondre à `GET /health`. Le seuil large est une vivacité, pas une disponibilité : un cycle lent (reset sur un long historique) ne doit pas faire redémarrer le worker. `/ready` reste le signal strict (trois cycles).
- **Frontend.** La configuration Nginx devient un modèle rendu au démarrage par l'entrypoint de l'image officielle (`envsubst`, variables filtrées `IPHI_*`) dans `/tmp`. La racine reste en lecture seule. `IPHI_API_UPSTREAM` (défaut `http://api:8000`) désigne l'API. Le résolveur DNS est lu dans `/etc/resolv.conf` du conteneur (`NGINX_ENTRYPOINT_LOCAL_RESOLVERS`), ce qui fonctionne sous Docker comme sous Kubernetes. Un healthcheck sert la page d'accueil.
- **Images.** Images de base épinglées par empreinte (reproductibles, aucune requête au registre une fois en cache), plus de directive `# syntax=` (l'analyseur intégré suffit), labels OCI, utilisateur non root, code en lecture seule pour cet utilisateur.
- **Compose** utilise les mêmes rôles (`migrate`, `worker`, `api` par défaut) : un seul chemin de démarrage, en développement comme hors Compose. La base reçoit `shm_size: 256mb` : les workers parallèles de PostgreSQL utilisent `/dev/shm`, limité à 64 Mo dans un conteneur.

## Alternatives écartées

- Un conteneur unique (superviseur lançant API et worker) : contraire à l'ADR 0001, mise à l'échelle et redémarrages confondus.
- Migration systématique au démarrage de l'API : plusieurs répliques se disputeraient le schéma, et un démarrage échouerait pour une migration longue.
- Fichier Nginx par environnement : une image par cible, au lieu d'une variable.
- Healthcheck du worker par la base (âge du heartbeat) : dépendrait de la base, alors qu'un orchestrateur doit juger le processus lui-même.

## Conséquences

- Sécurité inchangée : sans `IPHI_DEV_MUTATIONS=true`, l'image refuse les mutations (ADR 0007). Hors poste local, il faut laisser ce défaut jusqu'à US-11. Le garde repose sur `IPHI_BIND_HOST`, à renseigner avec l'adresse réellement publiée.
- Vérifié sans Compose (`docker run`, racine en lecture seule, capacités retirées) : API et worker démarrés ensemble avec migration au démarrage (une seule migration effective), trois conteneurs `healthy`, `/ready` 200 via Nginx, proxy rétabli 20 s après recréation de l'API.
- Ce n'est pas une revendication de mise en production : IPHI reste un démonstrateur simulé.
