# Finalisation — documentation, aide et interface bilingue

**Statut :** tâche finale demandée par le propriétaire le 19 novembre 2026 ; à réaliser **après US-12 MQTT**. Implémentation en cours de validation ; voir les résultats ci-dessous.

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

**État actuel :** README, guides débutants EN/FR, aide publique `/help`, aide contextuelle et traduction de présentation implémentés (ADR 0027). Vérifications statiques et démonstration sur base neuve réussies ; validation navigateur, captures et CI encore en cours. Ne pas déclarer le lot terminé avant la clôture des critères ci-dessus.
