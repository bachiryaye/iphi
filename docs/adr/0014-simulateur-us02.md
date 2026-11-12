# ADR 0014 — Simulateur US-02 : échantillonnage, empreinte, runs, horloge monotone, garde de mutation

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** US-02 (précise les ADR 0002, 0003 et 0007 ; complète le modèle de l'architecture §03.1)

## Contexte

L'ADR 0002 fixe le principe (horloge de plateforme, générateur pur à compteur) sans trancher ce qu'est un *tick*, ce que couvre l'empreinte golden, ni comment les runs se combinent. L'ADR 0007 exige une API « liée à 127.0.0.1 » alors qu'en conteneur uvicorn écoute toujours sur `0.0.0.0`. La réalisation impose aussi deux colonnes absentes du modèle §03.1.

## Décision

- **Tick = créneau d'échantillonnage de 5 s d'horloge de plateforme**, aligné sur l'époque Unix (`tick_of`, `tick_time`), indépendant de `IPHI_CYCLE_INTERVAL_S` : en mode accéléré, le collecteur (US-03) rattrape tous les ticks écoulés au lieu de produire des séries clairsemées.
- **Entrées du générateur :** seed, **clé** de composant, métrique, tick, runs couvrant le tick (`started_at ≤ t < stopped_at|ends_at`). Le statut d'un run n'est qu'une écriture comptable ; le temps décide. Bruit : BLAKE2b sur le quadruplet, sans état caché.
- **Empreinte golden** : SHA-256 d'une sérialisation canonique ; inclut clés de composant et de scénario, valeurs, unités, horodatages ; **exclut les UUID** (différents d'un environnement à l'autre). Valeur de référence : seed 42, `collector_down` sur `collector-01` dès le 2026-01-01T00:00:00Z, 120 ticks. Le CLI `python -m scripts.simulate` reproduit la même empreinte hors base.
- **Baseline permanent** : un run `baseline` (sans cible) est toujours actif ; il porte les observations non affectées par une panne, si bien que chaque observation a un `scenario_run_id`. Il ne se démarre ni ne s'arrête ; `reset` le remplace. Une panne active au plus par composant, un baseline actif par plateforme : **index uniques partiels**.
- **Attribution** : une observation est rattachée au run qui l'a façonnée (panne propre, sinon panne amont qui a modifié ses valeurs, sinon baseline).
- **Propagation** : seul un arrêt (`collector_down`) interrompt le flux ; `data_age_s` croît alors sur les composants aval qui l'exposent (historian, analytics). `stale_data` n'est volontairement pas propagé, pour respecter le résultat attendu « 1 incident freshness » tant que la suppression en aval (ADR 0005) ne couvre pas la classe `freshness`.
- **Signaux garantis par construction**, pas seulement en probabilité : `intermittent_loss` ne fait jamais échouer deux sondes consécutives (pas d'incident `availability` parasite) ; le baseline produit au plus une erreur par bloc de 60 s (jamais de déclenchement de R-ERR-001). Un test de propriété (Hypothesis) le vérifie sur des seeds arbitraires.
- **Horloge monotone** : chaque transition rebase les deux ancres ; `reset` repart de `max(heure murale, heure de plateforme)`. L'heure de plateforme ne recule jamais, donc d'anciens runs ne recouvrent jamais de nouveaux ticks. Conséquence assumée : après un passage en accéléré, l'heure de plateforme peut rester en avance sur l'heure murale.
- **Modèle** : `sim_clock.current_time` devient `anchor_platform_time` (`current_time` est un mot réservé SQL et la valeur n'est pas « l'heure courante » mais l'ancre) ; `scenario_run` gagne `number` (identité, affiché `#N` par le design system) et `ends_at` (fin planifiée ; le worker passe le run en `completed`).
- **Garde de mutation (ADR 0007)** : actives si `IPHI_DEV_MUTATIONS=true` **et** `IPHI_BIND_HOST` (adresse de publication des ports API et frontend dans Compose) est une adresse de bouclage. Compose active le mode dev par défaut ; le code le désactive par défaut. Mutations auditées `allowed`, refus de la garde `denied`, refus métier (409/422) `failed` avec le code d'erreur. La base reste publiée sur `127.0.0.1` quoi qu'il arrive.
- **Seed** : `python -m app.bootstrap` (service `migrate`) applique les migrations puis le seed idempotent (topologie, horloge, baseline).

## Alternatives écartées

- Tick = cycle du worker : la densité des séries dépendrait de la vitesse d'horloge.
- UUID dans l'empreinte : rend la preuve « deux environnements propres » impossible.
- `scenario_run_id` nullable hors panne : contredit la preuve US-02 « chaque observation porte `scenario_run_id` ».
- Plusieurs pannes simultanées sur un composant : sémantique ambiguë (quelle valeur prime ?) pour un gain de démonstration faible.
- Reset ramenant l'horloge à l'heure murale : d'anciens runs « dans le futur » recouvriraient les nouveaux ticks.

## Conséquences

- US-03 consomme `SimulationService.observations(first_tick, last_tick)` (≤ 720 ticks par appel) derrière l'interface `Connector`, et ajoute la purge des observations au `reset`.
- Toute modification du générateur, des profils ou du catalogue change l'empreinte golden : la mise à jour du test est un acte explicite.
- **Limites acceptées jusqu'à US-11** : la garde se fonde sur l'adresse **déclarée** (`IPHI_BIND_HOST`), un conteneur ne pouvant pas observer comment son port est publié ; une surcharge Compose qui publie autrement le port la contourne (usage non documenté, rappelé dans le README). Les refus `denied` ne sont pas limités en débit : la limitation arrive avec l'authentification (US-11, X-10).
- Un échec de l'étape simulation du cycle (plateforme non seedée, par exemple) n'écrit pas de battement : `/ready` passe en échec et la cause figure dans le log `worker.cycle_failed` (comportement US-01 conservé : jamais vert en aveugle).
- Le cycle worker n'écrit que lorsqu'un run arrive à échéance : sur ce poste, un commit coûte un `fdatasync` mesuré entre 35 ms et 1,8 s. US-03 devra garder **un seul commit par cycle** pour tenir l'objectif p95 < 500 ms (architecture §07.2).
