# Finalisation — documentation, aide et interface bilingue

**Statut :** tâche finale demandée par le propriétaire le 19 novembre 2026 ; à réaliser **après US-12 MQTT**. Implémentation validée ; livraison et contrôles consultables dans la [PR 15](https://github.com/bachiryaye/iphi/pull/15).

**Objectif :** permettre à un débutant de découvrir, lancer et utiliser IPHI sans accompagnement, et à un évaluateur de stage de comprendre rapidement le travail réalisé et ses limites.

Ce lot complète le [backlog de référence](03-backlog.md) sans modifier les identifiants US-01…US-12. Ordre demandé : terminer MQTT, puis livrer cette finalisation comme un résultat cohérent.

## README accessible et démonstration reproductible

- Présenter clairement le problème traité, les capacités vérifiées, l'architecture et le caractère simulé des équipements.
- Proposer une lecture rapide : prérequis, configuration locale, lancement, connexion et rôles, démonstration guidée, tests, arrêt et dépannage courant.
- Fournir des commandes exactes, les résultats attendus et des liens vers les explications détaillées ; ne jamais publier de mots de passe locaux.
- Prévoir un parcours court pour un recruteur : provoquer une panne, observer l'état, ouvrir l'incident et ses preuves, puis constater la récupération.
- Utiliser des captures de l'application réelle ; présenter les limites connues et distinguer le broker MQTT réel des équipements simulés.
- Conserver le README en anglais avec un résumé et un point d'entrée français, conformément à la politique documentaire existante.

## Page Aide / Documentation et parcours débutant

Créer un espace accessible depuis la navigation de l'application, avec une organisation et une lisibilité inspirées de **Mintlify** (référence interprétée à partir de « Mintify » dans la demande). Cela ne prescrit ni abonnement, ni nouveau service, ni copie de sa marque.

Le parcours doit expliquer, dans l'ordre : se connecter → comprendre la plateforme et ses états → lancer un scénario avec un rôle autorisé → consulter les composants et métriques → investiguer un incident et ses preuves → utiliser le diagnostic facultatif → observer la récupération → exporter un rapport.

Prévoir des étapes courtes, des exemples concrets, le résultat attendu de chaque action, un glossaire et un dépannage courant. Expliquer notamment `Unknown`, la fraîcheur des données, les unités, les horodatages et les différences entre un incident de la plateforme simulée et un problème du moniteur IPHI. Les parcours doivent tenir compte des droits viewer, engineer et admin.

## Aide contextuelle sur chaque page

Chaque page de l'outil doit proposer une section d'aide facile à trouver, expliquant son objectif, les données affichées, la manière de les interpréter et les actions disponibles selon le rôle. Des liens conduisent à la partie pertinente de la documentation et au parcours suivant. Les explications doivent rester courtes et adaptées à la page.

## Bascule français / anglais

- Ajouter un sélecteur de langue explicite avec préférence conservée ; garder les deux langues disponibles.
- Traduire les textes de navigation, boutons, formulaires, aides, libellés d'état, messages de chargement/vide/erreur et textes d'accessibilité.
- Conserver les identifiants techniques, clés de métriques, unités et valeurs canoniques des API ; traduire leur présentation sans modifier les règles métier ni les preuves stockées.
- Rendre le contexte de fuseau horaire explicite. Ne pas présenter des journaux ou diagnostics générés comme traduits si cette traduction n'existe pas.

La demande du propriétaire autorise cette évolution au-delà de l'interface uniquement anglaise de l'[ADR 0010](adr/0010-outillage-langue.md). Lors de l'implémentation, ajouter un ADR précisant la stratégie de traduction et actualiser les sections concernées de l'architecture et du design system. Les contrats API, le code et les commits restent en anglais.

## Critères d'acceptation de la tâche finale

1. Depuis un environnement propre, les commandes du README permettent le lancement, la connexion, la démonstration et les tests avec les résultats annoncés.
2. Le parcours débutant est vérifié dans l'application réelle, dans les deux langues, sans dépendre d'explications extérieures à la documentation ; les restrictions de rôle sont expliquées.
3. Chaque page possède une aide contextuelle pertinente et des liens valides vers la documentation.
4. La langue choisie persiste après rechargement ; les principaux parcours et leurs états d'erreur, vide et chargement sont vérifiés en français et en anglais.
5. La documentation et les aides sont utilisables au clavier, lisibles sur ordinateur et tablette, et respectent le design system et les contrôles d'accessibilité applicables.
6. Les captures correspondent à la version livrée, aucune information secrète n'est publiée, et les limites de simulation restent visibles.
7. Les vérifications pertinentes de lint, typage, tests et démonstration passent ; les résultats et éventuelles limites sont consignés avant de déclarer ce lot terminé.

## Preuves de validation

La source applicative `812a307` a passé les six contrôles de la [CI 44580461936](https://github.com/bachiryaye/iphi/actions/runs/44580461936). Les captures ci-dessous proviennent de son application réelle, après les premières évaluations du scénario nominal, avec un fournisseur IA désactivé.

| Critère | Résultat | Preuve |
|---|---|---|
| 1 — Lancement, connexion et démo | PASS | Base neuve, migrations, readiness et démonstration Compose en CI ; démo locale complète en 154 s |
| 2 — Parcours débutant EN/FR et rôles | PASS | Deux parcours navigateur réels : connexion engineer, panne, composant/métriques, preuves, diagnostic, CSV et récupération ; tests viewer/serveur conservés |
| 3 — Aide sur chaque page | PASS | Tests des liens contextuels de toutes les routes ; sommaire et ancres valides dans les deux langues |
| 4 — Préférence et états d’interface | PASS | Rechargement réel, filtre canonique conservé, formulaires, chargement/vide/erreur et restrictions de rôle testés |
| 5 — Clavier, ordinateur, tablette | PASS | Navigation clavier et focus vers le guide ; axe ; captures 1440/768 px et contrôle du débordement des libellés |
| 6 — Captures réelles et simulation visible | PASS | [Captures et reproduction](design/screenshots/README.md), formulaire vide, scénario nominal évalué ; anciens clichés identifiés comme historiques |
| 7 — Qualité et régressions | PASS | Lint/typage, tests frontend/backend, scénarios navigateur, captures, contrat API, images et secrets vérifiés en CI |

**Limites conservées :** les journaux, explications et diagnostics enregistrés restent dans leur langue d’origine ; les rapports PDF/CSV restent anglais. Aucun calcul métier, contrat API, schéma persistant ou connecteur n’est modifié par ce lot. Le seuil p95 sur sept jours et les blocages I/O de la machine locale restent documentés dans [performance.md](performance.md). Les captures de livraison ont été produites par la CI après des expirations locales DNS/Chromium ; aucune attente ni assertion métier n’a été assouplie.

**Livraison :** [PR 15 et ses contrôles](https://github.com/bachiryaye/iphi/pull/15). Les identifiants US-01…US-12 et leurs dépendances restent inchangés.

## Complément demandé le 20 novembre — autonomie du débutant et lisibilité

Le propriétaire demande un guide embarqué permettant à un novice d'utiliser l'outil
très facilement, avec les détails du parcours, des explications simples et une
typographie lisible. Ce complément conserve les routes, les règles métier et les
contrats existants. Il ne réouvre pas les critères déjà livrés comme s'ils avaient
été invalidés ; les preuves ci-dessus décrivent la livraison initiale.

- Transformer le parcours principal en six exercices avec actions numérotées et
  résultat observable à chaque étape ; expliciter les rôles et les boutons désactivés.
- Expliquer chaque écran, les règles, l'horloge, la récupération, les téléchargements,
  l'audit et les différences santé/statut/criticité/qualité/fraîcheur.
- Fournir un glossaire avec exemples, un dépannage par symptôme, les références
  industrielles et un parcours de présentation avec ses limites.
- Conserver l'anglais et le français, les anciennes ancres et l'accès avant connexion.
- Employer une police de lecture existante, des tailles relatives, un interligne
  aéré et une largeur limitée ; vérifier clavier, contrastes, tablette, repli et zoom.

**Preuves locales du complément :** `make lint typecheck` PASS ; 21 tests de l'aide
PASS (dont axe, navigation clavier, ancres, rôles et langues). Chrome réel sans
connexion : seize sujets, quatre actions pour la panne du collecteur, focus sur
la section choisie, IBM Plex Sans chargé, corps 16 px / 26 px à 1440 et 768 px.
Texte agrandi à 200 % : 32 px / 52 px sans débordement ; repli à 320 px sans
défilement horizontal. Les [captures actualisées](design/screenshots/README.md)
montrent l'introduction et les instructions réelles dans les deux langues/thèmes.

Les vérifications de livraison, notamment les parcours réels complets EN/FR,
figurent dans les [exécutions CI de la branche du complément](https://github.com/bachiryaye/iphi/actions?query=branch%3Adocs%2Fnovice-guide).
Les premières tentatives locales ont subi une forte pression disque, une expiration
à la création de page navigateur et une interruption de fermeture Vite ; ces
tentatives ne sont pas comptées comme des parcours réussis. Les attentes et
assertions métier sont conservées.
