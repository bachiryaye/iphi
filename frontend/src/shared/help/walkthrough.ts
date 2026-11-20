import type { HelpSection } from "./content";

export const walkthrough: Record<"en" | "fr", readonly HelpSection[]> = {
  en: [
    {
      id: "start",
      resources: [
        {
          href: "https://github.com/bachiryaye/iphi#try-it-locally",
          label: "Install IPHI: prerequisites and commands (GitHub)",
        },
      ],
      title: "Start here: sign in",
      body: "IPHI watches the services that carry industrial data. It helps you find a failing service, understand the evidence and keep an investigation record. All seven services and their faults are simulated. No industrial experience or AI account is needed for this guide.",
      result:
        "Installing IPHI yourself? The repository README explains prerequisites and make init-env / make up. Keep local credentials in your private .env, never in a screenshot or report. Use Sign out in the header when finished.",
      to: "/",
      steps: [
        {
          instruction:
            "Ask the demo owner for the application address, username and password. Open Sign in at the top of this guide.",
          result:
            "The sign-in form appears. There is no public registration and this guide contains no passwords.",
        },
        {
          instruction:
            "Choose English or Français, enter the supplied credentials and select Sign in once.",
          result:
            "Overview opens. Your language is saved in this browser. If you return to Sign in, use the troubleshooting section.",
        },
        {
          instruction: "Read your role in the application header before trying actions.",
          result:
            "Your role explains which controls are available. A disabled button does not mean that you made a mistake.",
        },
      ],
      entries: [
        {
          term: "viewer — explore",
          definition:
            "Read monitoring views, inspect incidents and download reports. Ask an engineer to create the fault so you can observe the exercise.",
        },
        {
          term: "engineer — follow the full exercise",
          definition:
            "Viewer access plus start/stop scenarios, change platform time, acknowledge/comment on incidents and request diagnoses.",
        },
        {
          term: "admin — administer the local demo",
          definition:
            "Engineer access plus reset and Audit. Reset is not needed for the normal beginner exercise.",
        },
      ],
      view: "Open the application",
    },
    {
      id: "states",
      title: "Read the platform state",
      body: "Read the status word and its explanation together; colour is an extra cue. Platform health describes the simulated services. Monitor status says whether IPHI itself is collecting and evaluating evidence. These are different signals.",
      result:
        "You can distinguish a fault in a simulated service from an IPHI collection problem. A stalled monitor is shown separately; silence cannot prove that a service is down.",
      to: "/",
      entries: [
        {
          term: "Healthy",
          definition:
            "Recent, usable evidence satisfies the rules. This does not promise that a future fault cannot occur.",
        },
        {
          term: "Warning",
          definition: "A rule confirms degradation, such as replies taking longer than allowed.",
        },
        {
          term: "Critical",
          definition:
            "A rule confirms a serious problem, such as failed active availability probes. Read the named rule for the reason.",
        },
        {
          term: "Unknown",
          definition:
            "Evidence is missing, too old or insufficient. This is not Healthy and does not by itself prove a service is down.",
        },
        {
          term: "Impacted / stale view",
          definition:
            "Impacted annotates a dependency problem without replacing the component’s own health. A stale view means a refresh failed: displayed values may be old.",
        },
      ],
      steps: [
        {
          instruction:
            "In Overview, read the explanation under platform health and compare the component rows.",
          result:
            "You can name the component and rule behind the problem. A critical component is not hidden by a healthy average.",
        },
        {
          instruction: "Check Monitor status and the last update before trusting the state.",
          result:
            "Unknown can be normal at startup while evidence windows fill. A stalled monitor requires investigation; an old healthy value is not current evidence.",
        },
      ],
      view: "Read platform health",
    },
    {
      id: "scenarios",
      title: "Exercise 1: create a collector fault",
      body: "A scenario deliberately changes synthetic signals. Start with one fault so its effects are easy to follow. You need engineer or admin access; viewer can observe but cannot start or stop a run. Explore the other catalog faults after completing this exercise.",
      result:
        "Realtime detection targets 15 seconds; a loaded machine can take longer. If nothing changes, check the monitor, active run, target, clock mode and filters before starting another fault.",
      to: "/scenarios",
      steps: [
        {
          instruction: "Open Scenarios. Check Active scenario runs and Overview before starting.",
          result:
            "For a clean exercise, only the baseline runs and all seven components are Healthy. Coordinate before changing another person’s running demo.",
        },
        {
          instruction:
            "Find Collector down, identified by collector_down. Keep Target on collector-01 and leave duration empty.",
          result:
            "The fault targets the collector. Empty duration means until stopped, not zero seconds.",
        },
        {
          instruction: "Select Start scenario once and check Active scenario runs.",
          result:
            "A collector_down row appears with its target and start time. Do not click repeatedly while the request is in progress.",
        },
        {
          instruction: "Open Overview, watch collector-01, then open its incident.",
          result:
            "The collector becomes Critical and one active availability incident appears with evidence. Downstream services may show impact. Repeated samples update that incident.",
        },
      ],
      view: "Open Scenarios",
    },
    {
      id: "metrics",
      title: "Exercise 2: understand the measurements",
      body: "A metric is a named measurement with a value, unit and timestamp. A log is a recorded message. A component page brings these observations together with the rules that interpreted them.",
      result:
        "An empty graph can simply mean no samples in the selected window. Check its dates and the platform clock. Metric keys and stored messages keep their original wording when you change language.",
      to: "/components",
      steps: [
        {
          instruction: "Open Components, then the collector-01 name.",
          result:
            "Its own health, deciding rule, dependencies, metric history and recent warning/error logs appear.",
        },
        {
          instruction:
            "In Metric history, select up, then probe_latency_ms. Check the time window and units.",
          result:
            "up = 1 means the active probe answered; up = 0 means it failed. probe_latency_ms is reply time in milliseconds: 1,000 ms = 1 s.",
        },
        {
          instruction:
            "Compare samples with recorded rule evaluations. Use View as table for exact rows.",
          result:
            "A gap is a missing sample, never a zero. A rule can evaluate several values over a time window, so one point does not always explain a state.",
        },
        {
          instruction:
            "Select an evaluation or evidence chip and inspect the linked observation and time.",
          result:
            "You connect the displayed state to a stored rule version and evidence instead of guessing from the graph.",
        },
      ],
      entries: [
        {
          term: "data_age_s — data freshness",
          definition:
            "Age of process data in seconds. A service can answer normally while serving old data: availability and freshness are different.",
        },
        {
          term: "good / uncertain / bad — measurement quality",
          definition:
            "Whether a measurement is usable, not whether the component is healthy. A good measurement of up = 0 supports a fault; bad samples are excluded from rule evidence.",
        },
      ],
      view: "Open Components",
    },
    {
      id: "incidents",
      title: "Exercise 3: investigate and acknowledge",
      body: "An incident keeps related signals together with a timeline and evidence. Its status is different from health: Open records a problem, Acknowledged means someone has taken responsibility, and Resolved means the incident has closed.",
      result:
        "Severity describes seriousness; status describes the incident lifecycle. Resolve is unavailable while the condition is active. A viewer can inspect everything here but cannot acknowledge, comment or diagnose.",
      to: "/incidents",
      steps: [
        {
          instruction:
            "Open Incidents, find the collector incident and open its title. Clear restrictive filters if it is missing.",
          result:
            "You see its component, severity, status, occurrence count and times. Occurrences are repeated signals, not separate failures.",
        },
        {
          instruction:
            "Read Signal, then Timeline, then Evidence chain. Select a citation such as E1.",
          result:
            "You can inspect the sample, log or evaluation that supports the explanation, including its time and rule version.",
        },
        {
          instruction:
            "With engineer/admin access, select Acknowledge if you are taking responsibility. Add a comment describing what you actually checked.",
          result:
            "The incident becomes Acknowledged and the timeline records the action. Acknowledging does not stop the fault, repair a service or erase evidence.",
        },
      ],
      view: "Open Incidents",
    },
    {
      id: "diagnosis",
      title: "Exercise 4: read a diagnosis critically",
      body: "Diagnose explains recorded evidence without AI. AI diagnosis is a separate optional action. Neither version decides health or performs repairs. Engineer/admin can request a diagnosis; all roles can read an existing one.",
      result:
        "A citation is a record to verify, not a guarantee of truth. Stored evidence and generated text keep their original language when you switch the interface language.",
      to: "/incidents",
      steps: [
        {
          instruction:
            "On the collector incident, select Diagnose and wait for the deterministic diagnosis panel.",
          result:
            "Facts, hypotheses, checks and limitations appear without an AI account, key or external provider.",
        },
        {
          instruction:
            "Read Facts and follow their citations. Compare a hypothesis with those facts.",
          result:
            "A fact reports an observation. A hypothesis is a possible, uncertain explanation. Two simultaneous events do not prove cause and effect.",
        },
        {
          instruction:
            "Read Checks and Limitations. If AI diagnosis is enabled, compare it with the deterministic version and inspect its citations too.",
          result:
            "Checks are investigation suggestions, not executed commands. An unavailable or rejected AI result leaves deterministic diagnosis and monitoring usable.",
        },
      ],
      view: "Return to Incidents",
    },
    {
      id: "recovery",
      title: "Exercise 5: stop the fault and observe recovery",
      body: "Stop restores nominal signals, but the rule still needs enough healthy observations to clear its time window and confirm recovery. Acknowledgement alone never restores a component.",
      result:
        "Do not use Reset for normal recovery. Admin Reset stops faults and clears simulated observations; incident evidence and audit remain. Read its confirmation and coordinate before resetting a shared demo.",
      to: "/scenarios",
      steps: [
        {
          instruction:
            "In Scenarios, find the collector_down row for collector-01 under Active scenario runs, then select Stop.",
          result:
            "That fault disappears from active runs. The baseline remains and nominal observations can resume.",
        },
        {
          instruction:
            "Watch Overview or the incident and wait. For a shorter demo, set Speed to 30 in Platform clock and select Run accelerated.",
          result:
            "Platform time advances at ×30. Old failures leave the rule window. Connectivity uses 300 s, so full recovery can take about five minutes of platform time.",
        },
        {
          instruction:
            "Check that the collector is Healthy and the original incident becomes Resolved. Include resolved incidents if the active-only list hides it.",
          result:
            "The same incident retains its timeline, evidence and diagnoses. It was resolved, not deleted.",
        },
        {
          instruction: "Return the clock mode to realtime after recovery.",
          result:
            "The next person can observe at normal speed. If health remains abnormal, check other active scenarios and the deciding rule.",
        },
      ],
      view: "Stop the simulated fault",
    },
    {
      id: "reports",
      title: "Exercise 6: download and explain a report",
      body: "An export is a snapshot of an incident and its existing diagnoses. Exporting never requests new AI analysis. Every role can export, including after resolution.",
      result:
        "Reports remain English. Retry a busy renderer later; oversized reports are refused explicitly rather than silently truncated. Evidence and timeline remain readable on screen.",
      to: "/incidents",
      steps: [
        {
          instruction:
            "Open the incident. Select Export PDF for a readable report or Export CSV for tabular evidence.",
          result:
            "A file named IPHI-INC-…-simulated downloads. Check the browser’s Downloads list if no file opens automatically.",
        },
        {
          instruction:
            "Open the file and check its incident ID, simulated source, UTC times, timeline and evidence register.",
          result:
            "You connect the export to your investigation. PDF is for reading; CSV can open in a spreadsheet or text editor.",
        },
        {
          instruction:
            "Explain which entries are facts, which are hypotheses and which checks remain to be done.",
          result:
            "The report records an investigation, not a real-plant fault or a completed repair.",
        },
      ],
      view: "Open an incident to export",
    },
  ],
  fr: [
    {
      id: "start",
      resources: [
        {
          href: "https://github.com/bachiryaye/iphi#try-it-locally",
          label: "Installer IPHI : prérequis et commandes (GitHub)",
        },
      ],
      title: "Commencer : se connecter",
      body: "IPHI surveille les services qui transportent des données industrielles. Il aide à trouver un service en difficulté, comprendre les preuves et conserver une investigation. Les sept services et leurs pannes sont simulés. Aucune connaissance industrielle ni compte IA n’est nécessaire pour suivre ce guide.",
      result:
        "Pour installer IPHI vous-même, le README du dépôt détaille les prérequis et make init-env / make up. Les identifiants restent dans votre fichier privé .env, jamais dans une capture ou un rapport. À la fin, utilisez Se déconnecter dans l’en-tête.",
      to: "/",
      steps: [
        {
          instruction:
            "Demandez au propriétaire l’adresse de l’application, votre identifiant et votre mot de passe. Ouvrez Se connecter en haut du guide.",
          result:
            "Le formulaire de connexion apparaît. Il n’y a pas d’inscription publique et ce guide ne contient aucun mot de passe.",
        },
        {
          instruction:
            "Choisissez Français ou English, saisissez les identifiants fournis et sélectionnez Se connecter une seule fois.",
          result:
            "La Vue d’ensemble s’ouvre. La langue reste mémorisée dans ce navigateur. Si vous revenez à la connexion, consultez le dépannage.",
        },
        {
          instruction: "Repérez votre rôle dans l’en-tête avant d’essayer les actions.",
          result:
            "Votre rôle explique les commandes disponibles. Un bouton grisé ne signifie pas que vous avez fait une erreur.",
        },
      ],
      entries: [
        {
          term: "viewer — découvrir",
          definition:
            "Consulter les écrans, examiner les incidents et télécharger les rapports. Demandez à un engineer de provoquer la panne pour observer le parcours.",
        },
        {
          term: "engineer — réaliser le parcours complet",
          definition:
            "Les droits viewer, plus démarrer/arrêter les scénarios, modifier l’horloge, prendre en compte/commenter les incidents et demander des diagnostics.",
        },
        {
          term: "admin — administrer la démo locale",
          definition:
            "Les droits engineer, plus réinitialiser et consulter Audit. La réinitialisation n’est pas nécessaire pour le parcours débutant normal.",
        },
      ],
      view: "Ouvrir l’application",
    },
    {
      id: "states",
      title: "Comprendre l’état de plateforme",
      body: "Lisez le mot d’état avec son explication ; la couleur est un repère supplémentaire. La santé de plateforme décrit les services simulés. L’État du moniteur indique si IPHI lui-même collecte et évalue les preuves. Ces deux informations sont différentes.",
      result:
        "Vous distinguez une panne d’un service simulé d’un problème de collecte IPHI. Un moniteur bloqué est signalé séparément ; le silence ne prouve pas qu’un service est arrêté.",
      to: "/",
      entries: [
        {
          term: "Sain",
          definition:
            "Les preuves récentes et utilisables satisfont les règles. Cela ne promet pas qu’aucune panne future ne peut survenir.",
        },
        {
          term: "Avertissement",
          definition:
            "Une règle confirme une dégradation, par exemple des réponses plus lentes que ce qui est autorisé.",
        },
        {
          term: "Critique",
          definition:
            "Une règle confirme un problème sérieux, par exemple des sondes de disponibilité en échec. Lisez la règle citée pour comprendre la raison.",
        },
        {
          term: "Inconnu",
          definition:
            "Les preuves manquent, sont trop anciennes ou insuffisantes. Ce n’est pas Sain et cela ne prouve pas à lui seul que le service est arrêté.",
        },
        {
          term: "Impacté / vue périmée",
          definition:
            "Impacté signale un problème de dépendance sans remplacer la santé propre du composant. Vue périmée signifie qu’une actualisation a échoué : les valeurs peuvent être anciennes.",
        },
      ],
      steps: [
        {
          instruction:
            "Dans Vue d’ensemble, lisez l’explication sous la santé globale et comparez les composants.",
          result:
            "Vous pouvez nommer le composant et la règle à l’origine du problème. Un composant critique n’est pas masqué par une moyenne saine.",
        },
        {
          instruction:
            "Vérifiez l’État du moniteur et la dernière actualisation avant de vous fier à l’état.",
          result:
            "Inconnu peut être normal au démarrage, pendant le remplissage des fenêtres de preuves. Un moniteur bloqué doit être investigué ; une ancienne valeur saine n’est pas une preuve actuelle.",
        },
      ],
      view: "Lire la santé de plateforme",
    },
    {
      id: "scenarios",
      title: "Exercice 1 : créer une panne du collecteur",
      body: "Un scénario modifie volontairement des signaux synthétiques. Commencez par une seule panne pour suivre facilement ses effets. Il faut un rôle engineer ou admin ; viewer peut observer, mais ne peut pas démarrer ni arrêter une exécution. Découvrez ensuite les autres pannes avec les descriptions du catalogue.",
      result:
        "L’objectif de détection en temps réel est de 15 secondes ; une machine chargée peut être plus lente. Si rien ne change, vérifiez le moniteur, le scénario actif, la cible, le mode d’horloge et les filtres avant de relancer une panne.",
      to: "/scenarios",
      steps: [
        {
          instruction:
            "Ouvrez Scénarios. Consultez Scénarios en cours et Vue d’ensemble avant de commencer.",
          result:
            "Pour un parcours propre, seul le scénario nominal fonctionne et les sept composants sont Sains. Échangez avant de modifier la démonstration d’une autre personne.",
        },
        {
          instruction:
            "Repérez Arrêt du collecteur, avec la clé collector_down. Gardez Cible sur collector-01 et laissez la durée vide.",
          result:
            "La panne concerne le collecteur. Une durée vide signifie jusqu’à l’arrêt, et non zéro seconde.",
        },
        {
          instruction:
            "Sélectionnez Démarrer le scénario une seule fois et consultez Scénarios en cours.",
          result:
            "Une ligne collector_down apparaît avec sa cible et l’heure de début. Ne cliquez pas plusieurs fois pendant l’envoi de la demande.",
        },
        {
          instruction: "Ouvrez Vue d’ensemble, observez collector-01, puis ouvrez son incident.",
          result:
            "Le collecteur devient Critique et un incident actif de disponibilité apparaît avec ses preuves. Les services en aval peuvent être impactés. Les mesures répétées complètent cet incident.",
        },
      ],
      view: "Ouvrir Scénarios",
    },
    {
      id: "metrics",
      title: "Exercice 2 : comprendre les mesures",
      body: "Une métrique est une mesure nommée, avec une valeur, une unité et une date. Un journal est un message enregistré. La fiche composant rassemble ces observations et les règles qui les interprètent.",
      result:
        "Un graphique vide peut simplement ne contenir aucun échantillon dans la période choisie. Vérifiez ses dates et l’horloge de plateforme. Les clés de métriques et les messages enregistrés gardent leur texte d’origine quand vous changez de langue.",
      to: "/components",
      steps: [
        {
          instruction: "Ouvrez Composants, puis le nom collector-01.",
          result:
            "Sa santé propre, la règle décisive, les dépendances, l’historique des métriques et les journaux d’avertissement/erreur récents apparaissent.",
        },
        {
          instruction:
            "Dans Historique des métriques, choisissez up, puis probe_latency_ms. Vérifiez la période et les unités.",
          result:
            "up = 1 signifie que la sonde active a reçu une réponse ; up = 0 qu’elle a échoué. probe_latency_ms est le temps de réponse en millisecondes : 1 000 ms = 1 s.",
        },
        {
          instruction:
            "Comparez les mesures aux évaluations enregistrées. Utilisez Afficher le tableau pour lire des lignes exactes.",
          result:
            "Un trou signifie un échantillon manquant, jamais un zéro. Une règle peut évaluer plusieurs valeurs sur une durée : un point isolé n’explique donc pas toujours l’état.",
        },
        {
          instruction:
            "Sélectionnez une évaluation ou une citation de preuve, puis consultez l’observation liée et sa date.",
          result:
            "Vous reliez l’état affiché à une version de règle et une preuve enregistrée, au lieu de deviner à partir du graphique.",
        },
      ],
      entries: [
        {
          term: "data_age_s — fraîcheur des données",
          definition:
            "L’âge des données du procédé, en secondes. Un service peut répondre normalement tout en fournissant des données anciennes : disponibilité et fraîcheur sont distinctes.",
        },
        {
          term: "good / uncertain / bad — qualité de mesure",
          definition:
            "Indique si la mesure est utilisable, pas si le composant est sain. Une bonne mesure de up = 0 étaye une panne ; les mesures bad sont exclues des preuves des règles.",
        },
      ],
      view: "Ouvrir Composants",
    },
    {
      id: "incidents",
      title: "Exercice 3 : investiguer et prendre en compte",
      body: "Un incident rassemble les signaux liés avec une chronologie et des preuves. Son statut est distinct de la santé : Ouvert signale un problème enregistré, Pris en compte qu’une personne s’en occupe, Résolu que l’incident est clos.",
      result:
        "La gravité décrit l’importance du problème ; le statut décrit son cycle de vie. Résoudre est indisponible tant que la condition est active. Un viewer peut tout examiner ici, mais ne peut pas prendre en compte, commenter ou diagnostiquer.",
      to: "/incidents",
      steps: [
        {
          instruction:
            "Ouvrez Incidents, retrouvez l’incident du collecteur et ouvrez son titre. Retirez les filtres restrictifs s’il manque.",
          result:
            "La fiche indique composant, gravité, statut, occurrences et dates. Les occurrences sont des signaux répétés, pas des pannes distinctes.",
        },
        {
          instruction:
            "Lisez Signal, puis Chronologie, puis Chaîne de preuves. Sélectionnez une citation comme E1.",
          result:
            "Vous consultez l’échantillon, le journal ou l’évaluation qui étaye l’explication, avec sa date et la version de règle.",
        },
        {
          instruction:
            "Avec un rôle engineer/admin, sélectionnez Prendre en compte si vous prenez l’investigation en charge. Ajoutez un commentaire sur ce que vous avez réellement vérifié.",
          result:
            "Le statut devient Pris en compte et l’action apparaît dans la chronologie. Cela n’arrête pas la panne, ne répare pas un service et n’efface pas les preuves.",
        },
      ],
      view: "Ouvrir Incidents",
    },
    {
      id: "diagnosis",
      title: "Exercice 4 : lire un diagnostic avec recul",
      body: "Diagnostiquer explique les preuves enregistrées sans IA. Diagnostic IA est une action facultative séparée. Aucune des deux versions ne décide de la santé et ne répare un service. Engineer/admin peut demander un diagnostic ; tous les rôles peuvent en lire un existant.",
      result:
        "Une citation est un enregistrement à vérifier, pas une garantie de vérité. Les preuves et textes produits gardent leur langue d’origine quand vous changez la langue de l’interface.",
      to: "/incidents",
      steps: [
        {
          instruction:
            "Sur l’incident du collecteur, sélectionnez Diagnostiquer et attendez le panneau de diagnostic déterministe.",
          result:
            "Faits, hypothèses, vérifications et limites apparaissent sans compte IA, clé ni fournisseur externe.",
        },
        {
          instruction:
            "Lisez les Faits et suivez leurs citations. Comparez une hypothèse à ces faits.",
          result:
            "Un fait rapporte une observation. Une hypothèse est une explication possible et incertaine. Deux événements simultanés ne prouvent pas un lien de cause à effet.",
        },
        {
          instruction:
            "Lisez Vérifications et Limites. Si Diagnostic IA est activé, comparez-le au déterministe et vérifiez aussi ses citations.",
          result:
            "Les vérifications sont des conseils d’investigation, pas des commandes exécutées. Un résultat IA indisponible ou rejeté laisse le diagnostic déterministe et la supervision utilisables.",
        },
      ],
      view: "Revenir aux incidents",
    },
    {
      id: "recovery",
      title: "Exercice 5 : arrêter la panne et observer le retour",
      body: "Arrêter rétablit les signaux nominaux, mais la règle attend encore assez d’observations saines pour vider sa fenêtre et confirmer le retour. Prendre en compte ne rétablit jamais un composant.",
      result:
        "N’utilisez pas Réinitialiser pour un retour normal. Cette action admin arrête les pannes et efface les observations simulées ; preuves d’incident et audit restent. Lisez sa confirmation et échangez avant de réinitialiser une démo partagée.",
      to: "/scenarios",
      steps: [
        {
          instruction:
            "Dans Scénarios, repérez la ligne collector_down de collector-01 sous Scénarios en cours, puis sélectionnez Arrêter.",
          result:
            "Cette panne disparaît des exécutions actives. Le scénario nominal reste et les observations normales peuvent reprendre.",
        },
        {
          instruction:
            "Observez Vue d’ensemble ou l’incident et patientez. Pour raccourcir la démo, réglez Vitesse sur 30 dans l’horloge puis sélectionnez Accélérer.",
          result:
            "La plateforme avance à ×30. Les anciennes pannes quittent la fenêtre de règle. La connectivité utilise 300 s : le retour complet peut prendre environ cinq minutes de plateforme.",
        },
        {
          instruction:
            "Vérifiez que le collecteur est Sain et que l’incident initial devient Résolu. Incluez les incidents résolus si la liste des actifs le masque.",
          result:
            "Le même incident conserve sa chronologie, ses preuves et ses diagnostics. Il a été résolu, pas supprimé.",
        },
        {
          instruction: "Remettez le mode d’horloge sur temps réel après le rétablissement.",
          result:
            "La personne suivante peut observer à vitesse normale. Si la santé reste anormale, vérifiez les autres scénarios actifs et la règle décisive.",
        },
      ],
      view: "Arrêter la panne simulée",
    },
    {
      id: "reports",
      title: "Exercice 6 : télécharger et expliquer un rapport",
      body: "Un export est un instantané d’un incident et de ses diagnostics existants. Il ne demande jamais de nouvelle analyse IA. Tous les rôles peuvent exporter, même après résolution.",
      result:
        "Les rapports restent en anglais. Réessayez plus tard si le moteur est occupé ; les rapports trop volumineux sont refusés explicitement, sans troncature silencieuse. Preuves et chronologie restent lisibles à l’écran.",
      to: "/incidents",
      steps: [
        {
          instruction:
            "Ouvrez l’incident. Sélectionnez Exporter PDF pour un rapport à lire ou Exporter CSV pour des preuves en tableau.",
          result:
            "Un fichier IPHI-INC-…-simulated se télécharge. Consultez les Téléchargements du navigateur si aucun fichier ne s’ouvre automatiquement.",
        },
        {
          instruction:
            "Ouvrez le fichier et vérifiez l’identifiant d’incident, l’origine simulée, les dates UTC, la chronologie et le registre des preuves.",
          result:
            "Vous reliez l’export à votre investigation. Le PDF se lit comme un document ; le CSV s’ouvre dans un tableur ou un éditeur de texte.",
        },
        {
          instruction:
            "Expliquez quels éléments sont des faits, des hypothèses et des vérifications restant à réaliser.",
          result:
            "Le rapport décrit une investigation, pas une panne d’usine réelle ni une réparation effectuée.",
        },
      ],
      view: "Ouvrir un incident à exporter",
    },
  ],
};
