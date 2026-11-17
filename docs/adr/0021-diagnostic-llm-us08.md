# ADR 0021 — US-08 : diagnostic LLM borné, comparaison et repli

- **Statut :** Acceptée (réalisation dans le périmètre US-08 approuvé)
- **Date :** 2026-11-17
- **Portée :** précise ADR 0006, architecture §06 et sécurité X-07/X-09/X-10

## Contexte

Le diagnostic déterministe et les colonnes de suivi LLM existent depuis US-05. Son service
verrouille l'incident pendant sa transaction. Ajouter un appel réseau à cet endroit bloquerait
le worker et les actions opérateur. Le fournisseur réel n'était pas encore choisi (ADR 0006).

## Décision

- Adaptateurs explicites derrière `Provider` : `none` par défaut, `fake` local sans réseau,
  `openai` via l'API Responses HTTPS officielle. Modèle et clé fournis par configuration ;
  aucun modèle payant par défaut. `httpx2`, déjà verrouillé pour les tests, passe en dépendance
  d'exécution (BSD-3-Clause, Python ≥ 3.11 ; compatible avec Python 3.14). Aucun SDK ni mécanisme automatique d'action n'est ajouté.
- L'endpoint réel est fixe ; pas d'URL fournie par la requête, pas de redirection, pas de proxy
  hérité de l'environnement. Aucun outil n'est exposé. `store=false` demande de ne pas conserver
  la réponse pour récupération via l'API ; cela ne constitue pas une garantie de rétention
  nulle chez le fournisseur.
- Une échéance globale de 20 s maximum englobe lecture de réponse et une nouvelle tentative
  maximum, seulement pour les erreurs transitoires. La réponse HTTP est limitée à 256 Ko et
  le texte à 64 Ko. Les plafonds configurables entrée/sortie bornent la consommation ; ils ne
  promettent pas un prix monétaire fixe, qui dépend du modèle choisi.
- L'entrée sélectionne les preuves immuables déjà attachées à l'incident (maximum 50 éléments,
  24 Ko). Le budget d'entrée utilise une borne conservatrice en octets UTF-8, incluant consigne,
  schéma et marge de protocole. Les éléments qui dépassent le budget sont omis et la limite est
  signalée. Les attributs de logs arbitraires sont exclus. Secrets et données personnelles
  reconnaissables (affectations de clés/mots de passe, bearer, clés connues, emails, IP et
  identifiants dans les URL) sont masqués avant émission et persistance.
- Les logs restent dans une valeur JSON échappée, délimitée explicitement comme non fiable.
  Pydantic interdit les champs supplémentaires, borne les listes et textes, et valide les
  incertitudes. Les labels `E<n>` sont résolus vers les IDs du paquet réellement envoyé.
  Citations inconnues supprimées ; affirmation sans citation restante supprimée et signalée.
  Des formulations causales certaines et commandes courantes sont également écartées.
  **Ce filtrage ne prouve ni la vérité sémantique d'une affirmation ni l'absence de toute
  formulation dangereuse.** La vérification humaine et l'absence de capacités d'action restent
  nécessaires ; le LLM ne modifie jamais la santé ou le cycle de vie d'un incident (D-19).
- Une connexion PostgreSQL dédiée en autocommit prend deux advisory locks non bloquants
  (acteur, incident). Elle est fermée physiquement à la sortie, ce qui libère ses verrous.
  Ils ne recouvrent ni le verrou du scheduler ni les lignes d'incident. Le budget est réservé
  et l'instantané est validé **avant** l'appel ; aucune transaction ou ligne d'incident n'est
  conservée pendant le réseau. Le résultat est ajouté dans une courte transaction finale.
- `diagnostic_budget` conserve une fenêtre fixe de 60 s par acteur, maximum six demandes LLM
  admises. La réservation survit au redémarrage et aux échecs. Une demande concurrente renvoie
  `409 DIAGNOSIS_IN_PROGRESS`, le dépassement `429 DIAGNOSIS_RATE_LIMITED`. Avant US-11, l'acteur
  est `dev-local`. Le mode déterministe reste disponible hors de ce quota.
- Une clé d'idempotence rejouée renvoie le diagnostic existant sans nouvel appel ni débit du
  budget. Réutiliser la clé dans un autre mode renvoie `409 DIAGNOSIS_KEY_CONFLICT`.
- Chaque tentative LLM conserve `status`, `error_code`, latence, consommation disponible,
  prompt masqué et hash de l'instantané. Les sorties brutes invalides ne sont pas conservées.
  `deterministic_id` référence la comparaison ou le repli déterministe produit du **même**
  instantané ; si le worker avance pendant l'appel, les preuves de cette lecture restent
  accessibles. Le hash porte l'instantané sélectionné avant réduction au budget de prompt.
- JSON invalide ⇒ `rejected`, panne réseau/timeout ⇒ `failed`, aucune affirmation factuelle
  retenue ⇒ `rejected`. Le résultat déterministe reste stocké séparément, jamais étiqueté comme
  produit par le LLM. L'UI affiche le repli immédiatement et la comparaison à la demande en
  cas de succès ; elle distingue aussi le faux fournisseur d'un vrai modèle.
- Le statut fournisseur provient de la dernière tentative persistée, sans appel réseau de
  surveillance. Avant toute tentative : `unknown`. Une panne IA est visible mais ne fait pas
  échouer `/ready` : les vérifications DB, schéma et worker continuent de déterminer la
  disponibilité de la supervision. Ce statut décrit la dernière tentative, pas une sonde actuelle.
- Migration additive 0007 : référence `diagnostic.deterministic_id`, index du dernier résultat
  LLM par fournisseur, table de budget. La liste des diagnostics renvoie les 50 plus récents
  et, si nécessaire, la comparaison du plus récent (maximum 51 éléments).
- `GET /incidents/{id}/evidence?evidence_id=N` charge une preuve citée sans parcourir les
  pages intermédiaires, en préservant son ordinal `E<n>` et son appartenance à l’incident.
  Le clic dans l’UI charge et surligne cette preuve, même après les 200 premiers éléments.
- La clé fournisseur n'est transmise qu'au conteneur API, jamais au worker, au frontend ni au
  job de migration. CI et démo utilisent `none` puis `fake` ; aucun coût externe requis.

## Alternatives écartées

- Appel sous `FOR UPDATE` de l'incident : empêche le worker d'avancer.
- Limite en mémoire : perdue au redémarrage et contournable avec plusieurs processus API.
- File de jobs et service séparé : non nécessaires pour une démo locale ; hors architecture.
- Texte brut de réponse conservé « pour debug » : pourrait conserver secrets ou injection.
- Faire confiance à une citation existante pour certifier une cause : une référence valide
  n'établit pas la vérité de l'affirmation.

## Conséquences et limites

Le délai global borne l’appel externe, pas les attentes de verrous ni les commits PostgreSQL.
Le thread HTTP et la connexion de garde restent occupés jusqu’au terme de la demande,
mais la transaction métier ne reste pas ouverte pendant le réseau. Un crash après l'appel et avant la
persistance peut conduire à un nouvel appel lors d'un rejeu : l'idempotence après résultat
persisté n'est pas une garantie « exactly once » chez le fournisseur. Le budget reste débité. Une nouvelle tentative réseau peut aussi être facturée
séparément : chaque demande admise produit au plus deux appels au fournisseur.
Une fenêtre fixe peut autoriser deux quotas rapprochés à sa frontière. Le masquage repose sur
des motifs reconnus et n'est pas un détecteur universel de données sensibles.

Le contrat du fournisseur est testé par transport local ; sa disponibilité, les sorties d'un
modèle réel et la facturation ne sont **pas vérifiées par ces tests**. Aucune clé ni aucun appel
payant n'est nécessaire à l'acceptation locale ou à CI.

Références : [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
