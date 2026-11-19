# Débuter avec IPHI

[English](getting-started.md) · [README](../README.md)

IPHI utilise uniquement des équipements simulés. Pour le lancer, installez Git, Docker avec Compose v2, GNU Make, Python 3.10+ et curl.

```sh
git clone https://github.com/bachiryaye/iphi.git
cd iphi
make demo IPHI_LLM_PROVIDER=none
```

Attendez `Demo passed in … s`, puis ouvrez http://127.0.0.1:8081. Le premier build télécharge les dépendances ; le parcours dure environ deux minutes après le build sur la machine de référence, davantage si le disque est chargé. Les ports 8081, 8001 et 5434 doivent être libres. L’aide est accessible avant connexion à http://127.0.0.1:8081/help.

Ouvrez le fichier privé `.env` dans un éditeur : pour `admin`, utilisez `IPHI_DEMO_ADMIN_PASSWORD` ; pour `engineer`/`viewer`, les entrées correspondantes. Ne publiez jamais ces valeurs. Choisissez **Français / English** dès la connexion ; la préférence persiste après rechargement.

## Commencer : se connecter

IPHI supervise une plateforme de données industrielles : sept services simulés acheminent les données depuis une source, via une passerelle et un collecteur, vers le stockage et l’analyse. Aucune usine réelle n’est connectée. Un compte local fourni par le propriétaire est nécessaire ; il n’y a pas d’inscription publique.

**À faire :** Ouvrez Connexion, saisissez votre identifiant et votre mot de passe, puis ouvrez Vue d’ensemble. Pour une installation locale, lancez make init-env puis make up depuis le dépôt ; les comptes générés figurent dans votre fichier privé .env.

**Résultat attendu :** La vue affiche sept composants, l’état de plateforme et celui du moniteur. Viewer peut consulter et exporter ; engineer peut lancer des scénarios, changer l’horloge, commenter et gérer les incidents ; admin peut aussi réinitialiser et consulter Audit.

## Comprendre l’état de plateforme

Sain indique que les preuves disponibles satisfont les règles. Avertissement et Critique indiquent qu’une règle a dépassé un seuil après sa période de confirmation. Inconnu signifie que les preuves sont absentes, périmées ou insuffisantes ; cet état ne signifie jamais Sain. L’impact est une annotation des dépendances, sans changer l’état propre du composant.

**À faire :** Dans Vue d’ensemble, lisez l’explication sous l’état global. Comparez-la à l’État du moniteur dans l’en-tête. Ouvrez un composant pour retrouver la règle décisive et les identifiants de preuves.

**Résultat attendu :** Vous distinguez une panne d’un service simulé d’un problème de collecte IPHI. Un moniteur bloqué est signalé séparément ; le silence ne prouve pas qu’un service est arrêté.

## Provoquer une panne du collecteur

Utilisez un compte engineer ou admin. Les scénarios modifient uniquement la simulation. Viewer voit le catalogue sans pouvoir démarrer ou arrêter une exécution. Chaque fiche indique sa clé technique, sa cible et le résultat attendu.

**À faire :** Ouvrez Scénarios. Sur Arrêt du collecteur (collector_down), gardez la cible collector-01 et laissez la durée vide, puis choisissez Démarrer le scénario une seule fois. Ouvrez Vue d’ensemble et attendez la confirmation de la panne par les règles.

**Résultat attendu :** collector-01 devient Critique et un seul incident actif de disponibilité apparaît avec ses preuves enregistrées. Les composants en aval peuvent être affectés. En temps réel, l’objectif de détection est de 15 s ; une machine chargée peut être plus lente. Les échantillons répétés mettent à jour le même incident.

## Examiner un composant et ses métriques

Composants liste les services ; Topologie montre leurs dépendances. Les flèches suivent les données d’une dépendance vers le composant qui en dépend. Une fiche composant réunit sa santé propre, les métriques, les évaluations enregistrées et les avertissements/erreurs récents.

**À faire :** Ouvrez Composants, puis collector-01. Examinez up et probe_latency_ms avec leurs unités. Utilisez la fenêtre temporelle ou Afficher le tableau ; sélectionnez une évaluation dans la bande d’états enregistrés et suivez sa preuve.

**Résultat attendu :** up = 0 indique l’échec d’une sonde active. Une lacune signifie qu’il n’y a pas d’échantillon ; elle n’est jamais tracée comme zéro. data_age_s mesure l’âge des données du procédé, distinct de l’absence de télémétrie. Les seuils portent sur l’agrégat d’une fenêtre de règle, pas forcément sur un point tracé.

## Examiner l’incident et ses preuves

Un incident regroupe les signaux répétés par empreinte. Il conserve sa chronologie, les versions de règles et les observations liées. Ses états sont Ouvert, Pris en compte et Résolu. Le prendre en compte ne répare pas le service simulé.

**À faire :** Ouvrez Incidents puis l’incident du collecteur. Lisez Signal, Chronologie et Chaîne de preuves. Sélectionnez une citation pour retrouver son échantillon, journal ou évaluation. Engineer/admin peut Prendre en compte et ajouter un commentaire ; viewer peut consulter ces éléments.

**Résultat attendu :** L’incident reste ouvert ou pris en compte tant que la condition persiste. Les identifiants de preuves et les clés canoniques restent identiques dans les deux langues. Les messages, commentaires et explications enregistrés sont affichés dans leur langue d’origine.

## Utiliser un diagnostic étayé

Le diagnostic explique les preuves enregistrées ; il ne décide jamais de la santé et n’exécute aucune remédiation. La version déterministe fonctionne sans modèle ni fournisseur réseau. La version IA facultative peut être désactivée, indisponible ou rejetée.

**À faire :** Avec un compte engineer/admin, choisissez Diagnostiquer sur l’incident. Lisez Faits, Hypothèses et incertitudes, Vérifications et Limites. Suivez les citations. Si un fournisseur IA est configuré, comparez son résultat à la lecture déterministe.

**Résultat attendu :** Chaque affirmation citée renvoie aux preuves de l’incident, mais une citation ne prouve pas sa vérité. Corrélation ne signifie pas causalité. Une panne du fournisseur laisse la supervision et le diagnostic déterministe disponibles. Le texte produit reste dans sa langue d’origine ; passer en français ne le traduit pas.

## Arrêter la panne et observer le rétablissement

Arrêter un scénario rétablit ses signaux nominaux. Les règles exigent une période stable (hystérésis), donc l’incident ne se ferme pas immédiatement. La prise en compte et la résolution manuelle sont deux opérations distinctes.

**À faire :** Dans Scénarios, trouvez l’exécution collector_down sous Scénarios en cours et choisissez Arrêter. Revenez à l’incident. Gardez le temps réel ou accélérez l’horloge avec un compte engineer/admin. N’utilisez pas Réinitialiser pour démontrer un rétablissement normal.

**Résultat attendu :** L’incident se résout automatiquement après le rétablissement des règles ; ses preuves restent disponibles. La connectivité utilise une fenêtre de 300 s : le rétablissement complet peut prendre environ cinq minutes de plateforme. Résoudre est indisponible tant que la condition est active. Réinitialiser exige admin et une confirmation distincte.

## Exporter l’investigation

Les rapports utilisent un instantané de l’incident et des diagnostics déjà enregistrés. Exporter n’appelle aucun modèle de langage. Les trois rôles peuvent exporter. Les fichiers signalent l’environnement simulé et utilisent des horodatages UTC.

**À faire :** Ouvrez l’incident et choisissez Exporter PDF ou Exporter CSV. Attendez le téléchargement par le navigateur. Consultez la synthèse, la chronologie, le registre des preuves et les diagnostics existants.

**Résultat attendu :** Un fichier nommé IPHI-INC-…-simulated est téléchargé. Le rapport reste en anglais et les preuves gardent leur langue d’origine. Un moteur de rendu occupé peut être réessayé ; un rapport trop volumineux est refusé explicitement, sans troncature silencieuse.

## Vocabulaire, unités et temps

La télémétrie désigne les mesures et journaux collectés. Une sonde vérifie activement qu’un service répond. La fraîcheur est l’âge des données du procédé (data_age_s), distinct de l’âge d’une réponse de supervision. Une évaluation conserve la version, la fenêtre, le seuil et les preuves expliquant l’état. La temporisation confirme un changement sur des évaluations consécutives ; l’hystérésis exige un rétablissement stable. L’empreinte regroupe les signaux répétés en un incident.

**À faire :** ms signifie millisecondes, s secondes, % pourcentage et count une quantité. L’horloge simulée pilote les observations et l’historique d’incidents ; UTC reste disponible et l’heure locale du navigateur est identifiée. Audit utilise l’UTC de l’horloge réelle. L’âge d’actualisation mesure celui de la réponse API.

**Résultat attendu :** Simulation est la source par défaut. MQTT est un transport réel facultatif de données synthétiques, sans intégration industrielle réelle. La langue modifie les libellés et les nombres, en conservant les clés techniques, unités, valeurs API et preuves.

## Si quelque chose semble incorrect

Inconnu au démarrage : laissez la collecte et les évaluations remplir les fenêtres. Moniteur bloqué ou erreur API : consultez la disponibilité et les journaux locaux ; un ancien point vert ne prouve pas la santé actuelle. Aucun incident : retirez les filtres ou lancez une panne avec un rôle autorisé.

**À faire :** 401 : reconnectez-vous. 403 : vérifiez le rôle ; admin est nécessaire pour réinitialiser et consulter Audit. 429 : attendez la fin de la limite avant de réessayer. IA désactivée : utilisez Diagnostiquer. Export occupé : réessayez ; trop volumineux : utilisez les listes de preuves/événements. Sans compte : contactez le propriétaire ou suivez le guide d’accès du dépôt. Port occupé : utilisez les ports alternatifs du README.

**Résultat attendu :** Réessayer conserve une erreur visible et affiche un identifiant de corrélation si l’API le fournit. Le message technique du serveur reste dans sa langue d’origine. La pression disque locale peut ralentir le démarrage, la collecte et les tests ; les limites mesurées figurent dans docs/performance.md.

## Tests et arrêt

Les commandes complètes et prérequis de développement figurent dans le [README](../README.md#tests-and-development). `make lint typecheck`, `make test-frontend` et `make test-e2e` vérifient respectivement la qualité statique, les composants et les parcours réels.

```sh
docker compose -p iphi-demo stop
# Conserver les données / garder le volume
make demo-down
# Supprimer la démo ET son volume
```

**`make demo` recrée aussi le volume de démo à chaque lancement.** Il ne supprime pas les données du projet de développement. Pour un usage persistant : `make up IPHI_LLM_PROVIDER=none` (interface 8080), puis `make down` conserve son volume. Voir [accès et rôles](access.md), [MQTT](mqtt.md), [performances et limites](performance.md).
