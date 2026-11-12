# ADR 0005 — Cycle de vie, déduplication et anti-tempête des incidents

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Le dossier fixait Open → Acknowledged → Resolved « avec réouverture documentée » sans préciser résolution automatique, réouverture, aggravation ni cascade aval. La déduplication doit résister aux accès concurrents.

## Décision

- Empreinte `sha256(platform_id|component_id|failure_class)` ; index unique partiel sur l'empreinte `WHERE status <> 'resolved'`.
- Une nouvelle occurrence met à jour l'incident actif (`last_seen_at`, `occurrence_count`, preuves).
- Sévérité aggravable (`severity_changed`), `peak_severity` conservée.
- Résolution automatique quand les règles de la classe sont revenues Healthy (après `clear_after`) ; résolution manuelle avec commentaire, refusée (409) si la condition persiste.
- Réouverture si la même empreinte réapparaît dans les 15 min (horloge de plateforme) ; sinon nouvel incident.
- Suppression aval : un composant dont une dépendance amont a un incident actif `availability`/`connectivity`/`telemetry_loss` antérieur est rattaché comme impact (événement `downstream_suppressed`) au lieu d'ouvrir un incident. Exception : `freshness` avec amont sain.
- Chronologie append-only `incident_event` (y compris commentaires) ; preuves jamais supprimées.

## Alternatives écartées

- Déduplication en mémoire : non robuste aux redémarrages et à la concurrence.
- Incident par composant impacté : tempête d'incidents (contraire au scénario obligatoire 5).
- Résolution manuelle uniquement : incidents fantômes après retour à la normale.

## Conséquences

- `collector_down` ⇒ exactement un incident actif, testé.
- La suppression aval peut masquer une seconde panne indépendante en aval : les preuves restent rattachées et visibles ; limite documentée.
