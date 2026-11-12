# ADR 0002 — Horloge de plateforme et simulation déterministe

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

US-02 exige « même scénario et même seed ⇒ événements reproductibles ». Avec l'heure murale et un scheduler, les valeurs dépendent du moment d'exécution et les tests e2e deviennent instables. La démo doit aussi pouvoir être accélérée.

## Décision

- Une horloge unique `PlatformClock` injectée (`core/clock.py`), modes `realtime`, `accelerated` (facteur), `manual` (avance sur commande). État persistant dans `sim_clock`.
- Interdiction d'appeler `datetime.now()` pour un horodatage métier (règle Ruff/test d'architecture).
- Générateur pur : `valeur = f(seed, composant, métrique, tick, scénarios actifs)` via un générateur pseudo-aléatoire à compteur (hachage stable du quadruplet) ; aucun état caché.
- Les scénarios sont des lignes `scenario_run` lues par le worker : l'API ne partage aucune mémoire avec lui.
- Audit : heure murale UTC + heure de plateforme.

## Alternatives écartées

- Simulation à état mutable en mémoire : non reproductible après redémarrage.
- `freezegun` dans les tests uniquement : ne résout pas la reproductibilité de la démo.

## Conséquences

- Test « golden » : hash identique des observations sur deux exécutions.
- En mode `realtime`, l'heure de plateforme suit l'heure UTC réelle depuis l'ancrage : la démo reste naturelle.
- Toute source réelle (US-12 ou futur) utilise l'horloge en mode `realtime` ; le mode `manual` est réservé à l'environnement `simulation`.
