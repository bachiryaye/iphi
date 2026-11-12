# ADR 0008 — Stockage : PostgreSQL standard, identifiants, rétention et sous-échantillonnage

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Volume estimé : 7 composants, ~60 séries, cycle 5 s ⇒ ~12 échantillons/s, ~1 M/jour. Une démo peut tourner plusieurs heures ou jours.

## Décision

- PostgreSQL 16 standard (pas d'extension TimescaleDB en V1) ; index composite (component_id, metric_name, observed_at desc) et BRIN sur observed_at.
- UUID v7 pour les entités métier ; `BIGINT IDENTITY` pour les observations.
- Rétention 7 jours (configurable) par job du worker ; les observations référencées comme preuves sont conservées ; incidents, événements, diagnostics et audit jamais purgés automatiquement.
- `GET /metrics` : sous-échantillonnage serveur par `date_bin` (min/avg/max), `max_points ≤ 2000`, fenêtre ≤ 7 jours ; aucune interpolation des trous.
- Pagination par curseur keyset.

## Alternatives écartées

- TimescaleDB : pertinent à plus grande échelle ; image et dépendance supplémentaires non nécessaires ici (évolution possible par ADR).
- Base séries temporelles séparée (InfluxDB…) : contraire à l'architecture approuvée.

## Conséquences

- Requêtes bornées par construction ; volume maîtrisé.
- Migration vers TimescaleDB possible sans changer le contrat d'API.
