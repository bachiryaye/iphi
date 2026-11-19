export type HelpTopic =
  | "start"
  | "states"
  | "scenarios"
  | "metrics"
  | "incidents"
  | "diagnosis"
  | "recovery"
  | "reports"
  | "glossary"
  | "troubleshooting";
export interface HelpSection {
  id: HelpTopic;
  title: string;
  body: string;
  action: string;
  result: string;
  to?: string;
}

export const sections: Record<"en" | "fr", readonly HelpSection[]> = {
  en: [
    {
      id: "start",
      title: "Start here: sign in",
      body: "IPHI monitors an industrial data platform: seven simulated services move data from a source through a gateway and collector to storage and analysis. No real plant is connected. You need a local account supplied by the demo owner; there is no public registration.",
      action:
        "Open Sign in, enter your username and password, then open Overview. For a local installation, run make init-env then make up from the repository; the generated accounts are in your private .env file.",
      result:
        "Overview shows seven components, a platform state and the monitor status. Viewer can inspect and export; engineer can run scenarios, change the clock, comment and manage incidents; admin can also reset the simulation and read Audit.",
      to: "/",
    },
    {
      id: "states",
      title: "Read the platform state",
      body: "Healthy means the available evidence satisfies the rules. Warning and Critical mean a named rule crossed a threshold after its confirmation period. Unknown means evidence is missing, stale or insufficient; it never means Healthy. Impact is an annotation from dependencies, not a change to the component’s own state.",
      action:
        "In Overview, read the explanation below the platform state. Compare it with Monitor status in the header. Open a component to find the deciding rule and evidence IDs.",
      result:
        "You can distinguish a fault in a simulated service from an IPHI collection problem. A stalled monitor is shown separately; silence cannot prove that a service is down.",
      to: "/",
    },
    {
      id: "scenarios",
      title: "Inject a collector fault",
      body: "Use an engineer or admin account. Scenarios change only the simulation. Viewer sees the catalog but cannot start or stop a run. Each card shows its technical key, target and expected result.",
      action:
        "Open Scenarios. On Collector down (collector_down), keep target collector-01 and leave duration empty, then choose Start scenario once. Open Overview and wait for the rules to confirm the fault.",
      result:
        "collector-01 becomes Critical and one active availability incident appears with stored evidence. Downstream components may show impact. In realtime the detection target is 15 s; a loaded machine can take longer. Repeated samples update the same incident.",
      to: "/scenarios",
    },
    {
      id: "metrics",
      title: "Inspect a component and its metrics",
      body: "Components lists the services; Topology shows their dependencies. Arrows follow the data from a dependency toward its dependent. A component page combines its own health, metric history, recorded rule evaluations and recent warning/error logs.",
      action:
        "Open Components, then collector-01. Inspect up and probe_latency_ms and their units. Use the time-window controls or View as table; use the recorded state band to select an evaluation and follow its evidence.",
      result:
        "up = 0 is a failed active probe. A gap means no sample; it is never drawn as zero. data_age_s measures the age of process data, which differs from missing monitoring telemetry. Thresholds apply to a rule’s window aggregate, not necessarily a single plotted point.",
      to: "/components",
    },
    {
      id: "incidents",
      title: "Investigate the incident",
      body: "An incident groups repeated signals by fingerprint. It preserves its timeline, rule versions and linked observations. The states are Open, Acknowledged and Resolved. Taking responsibility does not repair the simulated service.",
      action:
        "Open Incidents and the collector incident. Read Signal, Timeline and Evidence chain. Select an evidence chip to locate its sample, log or evaluation. Engineer/admin can Acknowledge and add an investigation comment; viewer can inspect all these records.",
      result:
        "The incident remains open or acknowledged while the condition persists. Evidence IDs and canonical keys stay unchanged in both interface languages. Stored messages, comments and explanations are shown in their original language.",
      to: "/incidents",
    },
    {
      id: "diagnosis",
      title: "Use diagnosis with evidence",
      body: "Diagnosis explains stored evidence; it never decides health or performs remediation. The deterministic version works without any model or network provider. The optional AI version can be disabled, unavailable or rejected.",
      action:
        "With an engineer/admin account, choose Diagnose on the incident. Read Facts, Hypotheses and their uncertainty, Checks and Limitations. Follow the citations. If an optional AI provider is configured, compare its result with the deterministic reading.",
      result:
        "Every cited claim links to incident evidence, but a citation alone does not prove the claim. Correlation is not causation. Provider failure leaves monitoring and deterministic diagnosis available. Generated text remains in its original language; switching to French does not translate it.",
      to: "/incidents",
    },
    {
      id: "recovery",
      title: "Stop the fault and observe recovery",
      body: "Stopping a scenario restores its nominal signals. Rules require a stable recovery period (hysteresis), so the incident does not close immediately. Acknowledgement and manual resolution are different operations.",
      action:
        "In Scenarios, find the collector_down run under Active scenario runs and choose Stop. Return to the incident. Keep realtime or use the accelerated clock with an engineer/admin account to shorten the wait. Do not use Reset to demonstrate normal recovery.",
      result:
        "The incident resolves automatically once its rules clear, and its evidence remains available. Connectivity uses a 300 s window, so full recovery can take about five minutes of platform time. Resolve is unavailable while the fault condition is active. Reset is an admin-only operation with a separate confirmation.",
      to: "/scenarios",
    },
    {
      id: "reports",
      title: "Export the investigation",
      body: "Reports use an existing snapshot of the stored incident and diagnoses. Exporting does not call a language model. All three roles can export. Files identify the simulated environment and use UTC timestamps.",
      action:
        "Open the incident and choose Export PDF or Export CSV. Wait for the browser download. Review the summary, timeline, evidence register and any existing diagnosis.",
      result:
        "A file named IPHI-INC-…-simulated is downloaded. Report content stays in English and stored evidence keeps its original language. A busy renderer can be retried; an oversized report is refused explicitly rather than silently truncated.",
      to: "/incidents",
    },
    {
      id: "glossary",
      title: "Vocabulary, units and time",
      body: "Telemetry is the measurements and logs collected by IPHI. A probe actively checks whether a service answers. Freshness is the age of the process data (data_age_s), not the age of the monitoring response. A rule evaluation records the version, window, threshold and evidence behind a state. Debounce confirms a change over consecutive evaluations; hysteresis requires stable recovery. A fingerprint groups repeated signals into one incident.",
      action:
        "Read ms as milliseconds, s as seconds, % as percent and count as a quantity. The simulated platform clock drives observations and incident history; UTC is always available and the browser’s local time is identified. Audit uses real wall-clock UTC. Refresh age describes the age of the API response.",
      result:
        "Simulation is the default source. MQTT is an optional real transport carrying synthetic observations, not proof of a real industrial integration. The language switch changes labels and number formatting while technical keys, units, API values and stored evidence remain intact.",
    },
    {
      id: "troubleshooting",
      title: "When something looks wrong",
      body: "Unknown after startup: allow collection and evaluation to populate the windows. A stalled monitor or API error: inspect readiness and the local service logs; do not interpret an old green sample as current health. No incidents: clear filters or start a fault with an authorized role.",
      action:
        "401: sign in again. 403: check your role; admin is required for reset and Audit. 429: wait for the rate limit before retrying. AI off: use Diagnose. Export busy: retry; oversized report: use the evidence/event lists. No account: ask the demo owner or follow the repository access guide. Port busy at startup: select the alternate ports documented in the README.",
      result:
        "Retry keeps the failure visible and displays a correlation ID when supplied by the API. The technical server message is preserved in its original language. Local disk pressure can delay startup, collection and tests; see docs/performance.md for the measured limits.",
    },
  ],
  fr: [
    {
      id: "start",
      title: "Commencer : se connecter",
      body: "IPHI supervise une plateforme de données industrielles : sept services simulés acheminent les données depuis une source, via une passerelle et un collecteur, vers le stockage et l’analyse. Aucune usine réelle n’est connectée. Un compte local fourni par le propriétaire est nécessaire ; il n’y a pas d’inscription publique.",
      action:
        "Ouvrez Connexion, saisissez votre identifiant et votre mot de passe, puis ouvrez Vue d’ensemble. Pour une installation locale, lancez make init-env puis make up depuis le dépôt ; les comptes générés figurent dans votre fichier privé .env.",
      result:
        "La vue affiche sept composants, l’état de plateforme et celui du moniteur. Viewer peut consulter et exporter ; engineer peut lancer des scénarios, changer l’horloge, commenter et gérer les incidents ; admin peut aussi réinitialiser et consulter Audit.",
      to: "/",
    },
    {
      id: "states",
      title: "Comprendre l’état de plateforme",
      body: "Sain indique que les preuves disponibles satisfont les règles. Avertissement et Critique indiquent qu’une règle a dépassé un seuil après sa période de confirmation. Inconnu signifie que les preuves sont absentes, périmées ou insuffisantes ; cet état ne signifie jamais Sain. L’impact est une annotation des dépendances, sans changer l’état propre du composant.",
      action:
        "Dans Vue d’ensemble, lisez l’explication sous l’état global. Comparez-la à l’État du moniteur dans l’en-tête. Ouvrez un composant pour retrouver la règle décisive et les identifiants de preuves.",
      result:
        "Vous distinguez une panne d’un service simulé d’un problème de collecte IPHI. Un moniteur bloqué est signalé séparément ; le silence ne prouve pas qu’un service est arrêté.",
      to: "/",
    },
    {
      id: "scenarios",
      title: "Provoquer une panne du collecteur",
      body: "Utilisez un compte engineer ou admin. Les scénarios modifient uniquement la simulation. Viewer voit le catalogue sans pouvoir démarrer ou arrêter une exécution. Chaque fiche indique sa clé technique, sa cible et le résultat attendu.",
      action:
        "Ouvrez Scénarios. Sur Arrêt du collecteur (collector_down), gardez la cible collector-01 et laissez la durée vide, puis choisissez Démarrer le scénario une seule fois. Ouvrez Vue d’ensemble et attendez la confirmation de la panne par les règles.",
      result:
        "collector-01 devient Critique et un seul incident actif de disponibilité apparaît avec ses preuves enregistrées. Les composants en aval peuvent être affectés. En temps réel, l’objectif de détection est de 15 s ; une machine chargée peut être plus lente. Les échantillons répétés mettent à jour le même incident.",
      to: "/scenarios",
    },
    {
      id: "metrics",
      title: "Examiner un composant et ses métriques",
      body: "Composants liste les services ; Topologie montre leurs dépendances. Les flèches suivent les données d’une dépendance vers le composant qui en dépend. Une fiche composant réunit sa santé propre, les métriques, les évaluations enregistrées et les avertissements/erreurs récents.",
      action:
        "Ouvrez Composants, puis collector-01. Examinez up et probe_latency_ms avec leurs unités. Utilisez la fenêtre temporelle ou Afficher le tableau ; sélectionnez une évaluation dans la bande d’états enregistrés et suivez sa preuve.",
      result:
        "up = 0 indique l’échec d’une sonde active. Une lacune signifie qu’il n’y a pas d’échantillon ; elle n’est jamais tracée comme zéro. data_age_s mesure l’âge des données du procédé, distinct de l’absence de télémétrie. Les seuils portent sur l’agrégat d’une fenêtre de règle, pas forcément sur un point tracé.",
      to: "/components",
    },
    {
      id: "incidents",
      title: "Examiner l’incident et ses preuves",
      body: "Un incident regroupe les signaux répétés par empreinte. Il conserve sa chronologie, les versions de règles et les observations liées. Ses états sont Ouvert, Pris en compte et Résolu. Le prendre en compte ne répare pas le service simulé.",
      action:
        "Ouvrez Incidents puis l’incident du collecteur. Lisez Signal, Chronologie et Chaîne de preuves. Sélectionnez une citation pour retrouver son échantillon, journal ou évaluation. Engineer/admin peut Prendre en compte et ajouter un commentaire ; viewer peut consulter ces éléments.",
      result:
        "L’incident reste ouvert ou pris en compte tant que la condition persiste. Les identifiants de preuves et les clés canoniques restent identiques dans les deux langues. Les messages, commentaires et explications enregistrés sont affichés dans leur langue d’origine.",
      to: "/incidents",
    },
    {
      id: "diagnosis",
      title: "Utiliser un diagnostic étayé",
      body: "Le diagnostic explique les preuves enregistrées ; il ne décide jamais de la santé et n’exécute aucune remédiation. La version déterministe fonctionne sans modèle ni fournisseur réseau. La version IA facultative peut être désactivée, indisponible ou rejetée.",
      action:
        "Avec un compte engineer/admin, choisissez Diagnostiquer sur l’incident. Lisez Faits, Hypothèses et incertitudes, Vérifications et Limites. Suivez les citations. Si un fournisseur IA est configuré, comparez son résultat à la lecture déterministe.",
      result:
        "Chaque affirmation citée renvoie aux preuves de l’incident, mais une citation ne prouve pas sa vérité. Corrélation ne signifie pas causalité. Une panne du fournisseur laisse la supervision et le diagnostic déterministe disponibles. Le texte produit reste dans sa langue d’origine ; passer en français ne le traduit pas.",
      to: "/incidents",
    },
    {
      id: "recovery",
      title: "Arrêter la panne et observer le rétablissement",
      body: "Arrêter un scénario rétablit ses signaux nominaux. Les règles exigent une période stable (hystérésis), donc l’incident ne se ferme pas immédiatement. La prise en compte et la résolution manuelle sont deux opérations distinctes.",
      action:
        "Dans Scénarios, trouvez l’exécution collector_down sous Scénarios en cours et choisissez Arrêter. Revenez à l’incident. Gardez le temps réel ou accélérez l’horloge avec un compte engineer/admin. N’utilisez pas Réinitialiser pour démontrer un rétablissement normal.",
      result:
        "L’incident se résout automatiquement après le rétablissement des règles ; ses preuves restent disponibles. La connectivité utilise une fenêtre de 300 s : le rétablissement complet peut prendre environ cinq minutes de plateforme. Résoudre est indisponible tant que la condition est active. Réinitialiser exige admin et une confirmation distincte.",
      to: "/scenarios",
    },
    {
      id: "reports",
      title: "Exporter l’investigation",
      body: "Les rapports utilisent un instantané de l’incident et des diagnostics déjà enregistrés. Exporter n’appelle aucun modèle de langage. Les trois rôles peuvent exporter. Les fichiers signalent l’environnement simulé et utilisent des horodatages UTC.",
      action:
        "Ouvrez l’incident et choisissez Exporter PDF ou Exporter CSV. Attendez le téléchargement par le navigateur. Consultez la synthèse, la chronologie, le registre des preuves et les diagnostics existants.",
      result:
        "Un fichier nommé IPHI-INC-…-simulated est téléchargé. Le rapport reste en anglais et les preuves gardent leur langue d’origine. Un moteur de rendu occupé peut être réessayé ; un rapport trop volumineux est refusé explicitement, sans troncature silencieuse.",
      to: "/incidents",
    },
    {
      id: "glossary",
      title: "Vocabulaire, unités et temps",
      body: "La télémétrie désigne les mesures et journaux collectés. Une sonde vérifie activement qu’un service répond. La fraîcheur est l’âge des données du procédé (data_age_s), distinct de l’âge d’une réponse de supervision. Une évaluation conserve la version, la fenêtre, le seuil et les preuves expliquant l’état. La temporisation confirme un changement sur des évaluations consécutives ; l’hystérésis exige un rétablissement stable. L’empreinte regroupe les signaux répétés en un incident.",
      action:
        "ms signifie millisecondes, s secondes, % pourcentage et count une quantité. L’horloge simulée pilote les observations et l’historique d’incidents ; UTC reste disponible et l’heure locale du navigateur est identifiée. Audit utilise l’UTC de l’horloge réelle. L’âge d’actualisation mesure celui de la réponse API.",
      result:
        "Simulation est la source par défaut. MQTT est un transport réel facultatif de données synthétiques, sans intégration industrielle réelle. La langue modifie les libellés et les nombres, en conservant les clés techniques, unités, valeurs API et preuves.",
    },
    {
      id: "troubleshooting",
      title: "Si quelque chose semble incorrect",
      body: "Inconnu au démarrage : laissez la collecte et les évaluations remplir les fenêtres. Moniteur bloqué ou erreur API : consultez la disponibilité et les journaux locaux ; un ancien point vert ne prouve pas la santé actuelle. Aucun incident : retirez les filtres ou lancez une panne avec un rôle autorisé.",
      action:
        "401 : reconnectez-vous. 403 : vérifiez le rôle ; admin est nécessaire pour réinitialiser et consulter Audit. 429 : attendez la fin de la limite avant de réessayer. IA désactivée : utilisez Diagnostiquer. Export occupé : réessayez ; trop volumineux : utilisez les listes de preuves/événements. Sans compte : contactez le propriétaire ou suivez le guide d’accès du dépôt. Port occupé : utilisez les ports alternatifs du README.",
      result:
        "Réessayer conserve une erreur visible et affiche un identifiant de corrélation si l’API le fournit. Le message technique du serveur reste dans sa langue d’origine. La pression disque locale peut ralentir le démarrage, la collecte et les tests ; les limites mesurées figurent dans docs/performance.md.",
    },
  ],
};
