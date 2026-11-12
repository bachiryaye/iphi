# ADR 0003 — Modèle d'observation : sondes actives, deux fraîcheurs, qualité, heure de réception

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Un service arrêté ne produit plus de métriques : sans précaution, « service down » (Critical attendu) et « plus de données » (Unknown attendu) sont indiscernables. Le dossier confondait aussi la fraîcheur de la télémétrie et celle des données procédé. Le cahier des charges demande une qualité de mesure.

## Décision

- Chaque connecteur sonde chaque composant à chaque cycle et émet toujours `up` (0/1) et `probe_latency_ms`. `up=0` ⇒ Critical ; absence de toute observation ⇒ Unknown + incident `telemetry_loss`.
- Deux fraîcheurs distinctes : télémétrie (âge de la dernière observation reçue, règle `R-TEL-001`) et données métier (`data_age_s`, règle `R-FRESH-001`).
- `metric_sample` porte `quality` (`good`/`uncertain`/`bad`), `observed_at` (temps d'événement) et `received_at` (temps d'ingestion), `source`, `scenario_run_id`, `collection_run_id`.
- Catalogue `metric_definition` : métrique, unité, plage ; toute observation non conforme est rejetée et comptée.
- Tolérances : futur > 30 s rejeté ; retard > 10 min rejeté ; doublon (composant, métrique, observed_at, source) ignoré.

## Alternatives écartées

- Inférer « down » de l'absence de données : confond panne et cécité du moniteur.
- Fraîcheur unique : rend le scénario « données obsolètes alors que le service répond » impossible à distinguer.

## Conséquences

- Le scénario `telemetry_blackout` devient testable et le moniteur ne peut plus être « vert » en aveugle.
- Les observations rejetées sont visibles dans `system/status`.
