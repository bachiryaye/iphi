# ADR 0004 — Évaluation de santé, agrégation par criticité et annotation d'impact

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Le cahier des charges demande une agrégation « pondérée par criticité » sans masquer un incident majeur ; la politique n'était pas définie, notamment pour Unknown. Une panne amont dégrade les composants aval, ce qui ne doit ni masquer la cause ni multiplier les alertes.

## Décision

- Règles typées (`threshold`, `freshness`, `absence`, `availability_ratio`), versionnées et immuables, définies dans `config/health_rules.yaml` (configuration versionnée dans Git, chargée au démarrage, lecture seule par l'API).
- Hystérésis : `raise_after` / `clear_after` évaluations consécutives et seuils de retour distincts ; état persistant dans `rule_state`.
- État composant = pire de ses règles, ordre `Critical > Unknown > Warning > Healthy`.
- État plateforme par priorités : (1) Critical d'un composant high/medium ⇒ Critical ; (2) Unknown d'un composant high ⇒ Unknown ; (3) tout autre Warning, Critical low, Unknown medium/low ⇒ Warning ; (4) sinon Healthy. Jamais de moyenne ; compteurs et justification renvoyés.
- Impact : annotation `impacted_by` (dépendances amont transitives Critical/Unknown), sans modifier l'état propre du composant.

## Alternatives écartées

- Score pondéré moyen : masque un composant critique en panne.
- Propager l'état Critical en aval : brouille la localisation de la cause.
- Règles éditables en base via l'interface : surface de sécurité et d'audit supplémentaire, non nécessaire en V1.

## Conséquences

- Tableau de priorité testé unitairement ; tests de propriété pour l'hystérésis.
- Modifier un seuil = nouvelle version de règle ; les évaluations passées restent explicables.
