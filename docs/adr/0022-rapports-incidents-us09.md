# ADR 0022 — US-09 : rapports d'incident sur un instantané borné

- **Statut :** Acceptée (réalisation dans le périmètre US-09 approuvé)
- **Date :** 2026-11-18
- **Portée :** précise ADR 0012, architecture §04.1 et sécurité X-08

## Contexte

Les pages d'incident embarquent les 200 premières preuves et les diagnostics récents. Un
rapport doit conserver les identifiants, les versions de règles et la distinction entre
faits et analyse, sans confondre cette première page avec un registre complet. Le worker
continue d'enrichir les incidents pendant l'export.

## Décision

- `GET /api/v1/reports/incidents/{id}?format=pdf|csv` (PDF par défaut), lecture accessible
  sans garde de mutation ; rôle viewer à partir d'US-11. Réponse en pièce jointe, nom dérivé
  de la référence interne, `Cache-Control: no-store`, `X-IPHI-Environment: simulation`.
- Lecture PostgreSQL `REPEATABLE READ, READ ONLY` via les interfaces publiques des modules
  incidents et diagnostics. Aucun verrou de ligne et transaction fermée avant le rendu.
  La topologie, immuable en fonctionnement nominal, est lue par son service public.
- Même modèle de présentation pour PDF et CSV : résumé, chaque événement et preuve, règles
  versionnées effectivement citées, dernier diagnostic de chaque type et comparaison
  déterministe du dernier résultat IA si différente. Aucun nouveau diagnostic à l'export ;
  aucun prompt, secret fournisseur ou réponse brute exporté.
- Registre complet jusqu'à 1 000 preuves et 1 000 événements. Dépassement : `413
  REPORT_TOO_LARGE`, sans troncature silencieuse ; les endpoints paginés restent accessibles.
  Limites supplémentaires : contenu HTML 2 Mo, PDF 100 pages, téléchargement 8 Mo. CSV peut
  être utilisé si seule la limite de pages PDF est atteinte.
- PDF : WeasyPrint 70, Jinja2 avec auto-échappement explicite et variables indéfinies
  refusées, Pango dans l'image. Modèle A4 clair, tokens d'impression issus du design system,
  polices IBM Plex locales (licence OFL jointe), bannière de simulation sur chaque page,
  horodatages ISO-8601 UTC. L'heure de génération murale est distinguée des heures simulées.
- Le chargeur de ressources accepte uniquement trois URI exactes de polices embarquées.
  Toute URL réseau, `file:`, `data:` ou chemin arbitraire est refusée. Texte des logs et
  diagnostics uniquement dans des nœuds HTML échappés, jamais dans le CSS ni des URL.
- Un seul rendu PDF simultané par processus API ; un second reçoit `503 REPORT_BUSY`,
  réessayable. Le CSV et la supervision restent disponibles. Pas de file de jobs ni de
  service supplémentaire. Les limites bornent le travail ; ce n'est pas une garantie
  universelle de temps CPU pour tout contenu. L'authentification reste celle de l'ADR 0007.
- CSV UTF-8 avec BOM, champs tous entre guillemets, colonne `record_type`. Une ligne par
  preuve/événement, plus les lignes de résumé, règle, métadonnées et affirmations de
  diagnostic. `environment`, incident et heure d'export répétés sur chaque ligne. Cellules
  commençant par `= + - @`, tabulation ou retour ligne neutralisées par une apostrophe ;
  espaces/BOM initiaux pris en compte. L'apostrophe est une protection de présentation,
  pas une modification des valeurs persistées.
- Commandes explicites **Export PDF / Export CSV** : disponibles en lecture seule, état
  occupé pendant la demande, erreurs structurées avec corrélation, nouvel essai possible.
  Téléchargement binaire via le client généré ; URL de blob libérée après son démarrage.
- Dépendances d'exécution ajoutées : WeasyPrint (BSD), Jinja2 (BSD) ; pypdf (BSD), uniquement
  en développement, extrait le texte pour vérifier les PDF. Versions verrouillées.

## Alternatives écartées

- Export des 200 premières preuves sans avertissement : rapport incomplet présenté comme
  exhaustif. Export illimité : coût mémoire et rendu non bornés.
- Plusieurs lectures paginées indépendantes : peuvent mélanger des états différents.
- Naviguer directement vers une URL de téléchargement : une réponse d'erreur pourrait être
  enregistrée comme un PDF au lieu d'être expliquée dans l'interface.
- Liens ou HTML issus des messages : risque d'injection et de chargement de ressources.

## Vérification et limites

Tests du contenu sur PostgreSQL réel, comparaison des IDs et du nombre de lignes, extraction
du texte PDF, cas IA fake et repli, injection CSV/HTML, accès aux ressources refusé,
dépassement explicite et téléchargement navigateur. Revue visuelle du PDF rendu en images.
La provenance d'une affirmation IA ne prouve pas sa vérité ; sa vérification reste humaine.
Le balisage PDF est activé, sans prétendre à une certification d'accessibilité PDF/UA.

Références : [WeasyPrint : installation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html),
[API et URL fetchers](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html),
[auto-échappement Jinja2](https://jinja.palletsprojects.com/en/stable/api/#autoescaping).
