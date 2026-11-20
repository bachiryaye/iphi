import type { HelpSection } from "./content";

export const reference: Record<"en" | "fr", readonly HelpSection[]> = {
  en: [
    {
      id: "tour",
      title: "Find your way around the screens",
      body: "Start with the overview, then open the service or incident you want to understand. The left menu changes views. The header shows platform time, monitor status and your account. On narrow screens the menu uses icons; each keeps an accessible name and a hover label.",
      entries: [
        {
          term: "Overview",
          definition:
            "The starting point: platform health, seven components and active incidents. Open a component name for measurements or an incident title for investigation.",
        },
        {
          term: "Topology",
          definition:
            "The dependency map. Arrows go from a service supplying data to a service consuming it. The table offers the same navigation without using the graph.",
        },
        {
          term: "Components",
          definition:
            "Find a service with state, type and criticality filters; its name opens its detail page. Criticality is its importance, whereas health is its current assessed condition.",
        },
        {
          term: "Incidents",
          definition:
            "Find present and past problems. Filters can hide results: check status, severity and component before concluding that nothing happened.",
        },
        {
          term: "Scenarios",
          definition:
            "Deliberately create and stop simulated faults. This is where the practical exercise begins. The same screen controls simulated time.",
        },
        {
          term: "Rules",
          definition:
            "Read the metric, window, thresholds and confirmation counts behind a state. The catalog is read-only.",
        },
        {
          term: "Help / Audit",
          definition:
            "Help is this public guide. Audit is admin-only and records sensitive actions and refusals, separately from an incident’s timeline.",
        },
      ],
      action:
        "Open Help for this page on any application view for a short explanation and a link here. Use the contents or your browser’s Find command to locate a topic.",
      result:
        "You can keep this guide in another tab and return to the application without losing the instructions.",
      to: "/",
      view: "Open Overview",
    },
    {
      id: "rules",
      title: "Read the rule behind a state",
      body: "A rule is an explicit test, not an AI opinion. Its version records which definition was applied. The Rules screen explains active versions; it does not offer editing.",
      steps: [
        {
          instruction: "Open Rules and find R-AVAIL-001, also shown in the collector incident.",
          result:
            "The key and version connect the catalog to the evaluation stored with the incident.",
        },
        {
          instruction: "Read Measure, Warning (clear), Critical (clear), then Raise / clear.",
          result:
            "Measure names the value and window. Parentheses contain recovery thresholds. Raise / clear counts consecutive evaluations, not seconds.",
        },
        {
          instruction: "Read Rationale and recommendation before proposing a check.",
          result:
            "You can explain why the condition matters and which investigation check to try. These are demonstration thresholds, not real-plant settings.",
        },
      ],
      action: "Compare a stored evaluation with the rule’s definition.",
      result:
        "Confirmation avoids reacting to one noisy sample; hysteresis prevents rapid back-and-forth changes. No usable evidence produces Unknown rather than a passed rule.",
      to: "/rules",
      view: "Open Rules",
    },
    {
      id: "clock",
      title: "Understand time before accelerating it",
      body: "Observations and incident history use simulated platform time. Audit and session security use real time. Acceleration shortens demonstration waits; it is not a performance benchmark. Engineer/admin can change the clock; every role can read it.",
      entries: [
        {
          term: "realtime",
          definition:
            "Platform time advances with real elapsed time. Start here when learning how faults develop.",
        },
        {
          term: "accelerated",
          definition:
            "Platform time runs faster. At ×30, roughly 30 platform seconds pass per real second; computation and refreshes still take real time.",
        },
        {
          term: "manual",
          definition:
            "Platform time waits for an explicit Advance 30 s action. Check this mode if the exercise seems frozen.",
        },
        {
          term: "UTC and local time",
          definition:
            "UTC is a shared time reference. Local time depends on the browser’s zone. Compare timestamps in the same zone, and distinguish an observation’s time from the last API refresh.",
        },
      ],
      action:
        "In Scenarios, inspect Platform clock. Keep realtime for the first fault; use acceleration at the recovery step, then restore realtime.",
      result:
        "The visible mode and multiplier explain how the graphs and rule windows advance. Changing the clock affects everyone using this local demo.",
      to: "/scenarios",
      view: "Inspect Platform clock",
    },
    {
      id: "audit",
      title: "Admin: read the audit trail",
      body: "Audit records sensitive actions and denied attempts: who acted, which action, its result and its time. It does not replace the incident timeline and is not a list of industrial machine alarms.",
      steps: [
        {
          instruction:
            "With an admin account, open Audit. Choose action/outcome filters or a UTC time interval if needed.",
          result: "The list narrows to matching events. Viewer/engineer cannot access this screen.",
        },
        {
          instruction:
            "Read an event’s actor, action, outcome and time. Move to the next page for older results.",
          result:
            "You can distinguish an allowed action from a refusal. Technical action codes remain unchanged in either language.",
        },
      ],
      action:
        "Compare an action you performed with its audit entry without confusing simulated and real time.",
      result:
        "Audit uses real wall-clock UTC and survives simulation reset. Incident-specific comments and evidence remain in that incident’s timeline.",
      to: "/audit",
      view: "Open Audit (admin only)",
    },
    {
      id: "standards",
      resources: [
        {
          href: "https://github.com/bachiryaye/iphi/blob/main/docs/industrial-references.md",
          label: "Detailed industrial references and sources (GitHub)",
        },
      ],
      title: "Industrial references behind the design",
      body: "These references guided selected design choices. IPHI is an independent simulated demonstrator, not a certified industrial product. Here is what you can actually show.",
      entries: [
        {
          term: "ISA-95 / IEC 62264 — responsibilities",
          definition:
            "Vocabulary for an industrial data chain: source, gateway, collector, historian and consuming services have different roles. Seven services do not mean seven ISA-95 levels.",
        },
        {
          term: "ISA-101 — readable HMI",
          definition:
            "HMI means human-machine interface: the screens and controls. IPHI uses restrained presentation, abnormal-state emphasis, and status words/shapes as well as colour. The exact IPHI palette is a design choice, not a certification.",
        },
        {
          term: "ISA-18.2 / IEC 62682 — alarm-management ideas",
          definition:
            "Explain rules, confirm changes, avoid repeated duplicate incidents, acknowledge responsibility and keep history. IPHI incidents are platform problems, not a full process-safety alarm system.",
        },
        {
          term: "ISA/IEC 62443 — boundaries and least privilege",
          definition:
            "OT means operational technology: site equipment and its controls. Roles are enforced by the server; there are no OT writes or automatic repairs. The local demo does not establish a security level or validated industrial zones/conduits.",
        },
        {
          term: "OPC UA quality semantics — usable measurements",
          definition:
            "good, uncertain and bad describe observation quality, separately from health. This three-label abstraction is not an OPC UA adapter. The optional implemented transport is MQTT carrying synthetic observations.",
        },
      ],
      action:
        "Connect one principle to a screen: status shapes, rule confirmation, one incident for repeated signals, or viewer restrictions. The repository’s docs/industrial-references.md links these choices to official sources, code and tests.",
      result:
        "You can explain which principles you used and their limits without claiming full conformity, real-plant compatibility or certification.",
    },
    {
      id: "presentation",
      resources: [
        {
          href: "https://github.com/bachiryaye/iphi#recorded-demonstration",
          label: "Watch the recorded walkthrough (GitHub)",
        },
      ],
      title: "Present IPHI and check what you learned",
      body: "Use the same evidence-backed exercise for an interview. Prepare a healthy baseline and an engineer account before starting. Timing varies by machine; the recorded three-minute video contains cuts and accelerated recovery.",
      steps: [
        {
          instruction:
            "Explain the problem on Overview: a broken data service can make industrial information unavailable or old. State clearly that all equipment is simulated.",
          result:
            "Your audience understands what IPHI monitors and what it does not claim to connect to.",
        },
        {
          instruction:
            "Start Collector down, open the resulting incident, follow a rule and a piece of evidence, then request the deterministic diagnosis.",
          result:
            "You show the path from observation to a justified state and investigation, without requiring an AI provider.",
        },
        {
          instruction:
            "Stop the scenario, disclose any clock acceleration, show stable recovery and export a report.",
          result:
            "You demonstrate the full lifecycle and retained evidence. Explain that monitoring needs no LLM, that hypotheses are uncertain and that IPHI never repairs real equipment.",
        },
      ],
      entries: [
        {
          term: "Can I explain Unknown?",
          definition:
            "Yes: insufficient usable evidence, never automatically Healthy or proof of a down service.",
        },
        {
          term: "Can I explain Acknowledge versus Stop?",
          definition:
            "Acknowledge records responsibility; Stop removes the simulated fault. Stable evidence is still needed for recovery.",
        },
        {
          term: "Can I prove a displayed conclusion?",
          definition:
            "Open its rule version and observation/evidence references. Explain facts, hypotheses and remaining checks separately.",
        },
      ],
      action:
        "Follow the six exercises once yourself. If any answer is unclear, revisit the linked topic before presenting.",
      result:
        "You can demonstrate the tool and explain its limits. The repository README provides the native GitHub video, transcript, setup instructions and the detailed industrial-reference guide.",
    },
  ],
  fr: [
    {
      id: "tour",
      title: "Se repérer dans les écrans",
      body: "Partez de la vue générale, puis ouvrez le service ou l’incident à comprendre. Le menu à gauche change de vue. L’en-tête indique l’heure de plateforme, le moniteur et votre compte. Sur écran étroit, le menu utilise des icônes ; chacune garde un nom accessible et une indication au survol.",
      entries: [
        {
          term: "Vue d’ensemble",
          definition:
            "Le point de départ : santé globale, sept composants et incidents actifs. Ouvrez le nom d’un composant pour ses mesures ou le titre d’un incident pour l’investigation.",
        },
        {
          term: "Topologie",
          definition:
            "La carte des dépendances. Les flèches partent du service qui fournit les données vers celui qui les consomme. Le tableau permet la même navigation sans utiliser le graphe.",
        },
        {
          term: "Composants",
          definition:
            "Retrouvez un service avec les filtres d’état, type et criticité ; son nom ouvre sa fiche. La criticité est son importance, tandis que la santé est sa situation évaluée actuellement.",
        },
        {
          term: "Incidents",
          definition:
            "Retrouvez les problèmes présents et passés. Les filtres peuvent masquer des résultats : vérifiez statut, gravité et composant avant de conclure qu’il ne s’est rien passé.",
        },
        {
          term: "Scénarios",
          definition:
            "Créez volontairement une panne simulée, puis arrêtez-la. Le parcours pratique commence ici. Cet écran commande aussi le temps simulé.",
        },
        {
          term: "Règles",
          definition:
            "Lisez la mesure, la fenêtre, les seuils et les confirmations qui expliquent un état. Le catalogue est en lecture seule.",
        },
        {
          term: "Aide / Audit",
          definition:
            "Aide est ce guide public. Audit est réservé aux admins et conserve les actions sensibles et refus, séparément de la chronologie d’un incident.",
        },
      ],
      action:
        "Sur chaque page de l’application, ouvrez Aide pour cette page pour une explication courte et un lien ici. Utilisez le sommaire ou la recherche du navigateur pour retrouver un sujet.",
      result:
        "Vous pouvez garder ce guide dans un autre onglet et revenir à l’application sans perdre les consignes.",
      to: "/",
      view: "Ouvrir la Vue d’ensemble",
    },
    {
      id: "rules",
      title: "Lire la règle derrière un état",
      body: "Une règle est un test explicite, pas un avis de l’IA. Sa version conserve la définition utilisée. L’écran Règles explique les versions actives ; il ne propose pas de modification.",
      steps: [
        {
          instruction:
            "Ouvrez Règles et repérez R-AVAIL-001, aussi visible dans l’incident du collecteur.",
          result:
            "La clé et la version relient le catalogue à l’évaluation conservée avec l’incident.",
        },
        {
          instruction:
            "Lisez Mesure, Avertissement (rétablissement), Critique (rétablissement), puis Déclenchement / rétablissement.",
          result:
            "Mesure précise la valeur et la fenêtre. Les parenthèses indiquent les seuils de retour. Déclenchement / rétablissement compte des évaluations consécutives, pas des secondes.",
        },
        {
          instruction: "Lisez la justification et la recommandation avant de proposer un contrôle.",
          result:
            "Vous expliquez pourquoi la condition compte et quelle vérification essayer. Les seuils sont ceux de la démonstration, pas d’une usine réelle.",
        },
      ],
      action: "Comparez une évaluation enregistrée à la définition de sa règle.",
      result:
        "La confirmation évite de réagir à un échantillon bruité ; l’hystérésis empêche des changements aller-retour rapides. Sans preuve utilisable, la règle produit Inconnu.",
      to: "/rules",
      view: "Ouvrir Règles",
    },
    {
      id: "clock",
      title: "Comprendre le temps avant de l’accélérer",
      body: "Observations et historique d’incidents utilisent le temps simulé de plateforme. Audit et la sécurité des sessions utilisent le temps réel. L’accélération raccourcit les attentes de démo ; elle ne mesure pas une performance. Engineer/admin peut changer l’horloge ; tous les rôles peuvent la lire.",
      entries: [
        {
          term: "realtime — temps réel",
          definition:
            "Le temps de plateforme avance avec le temps réellement écoulé. Commencez ici pour apprendre le déroulement d’une panne.",
        },
        {
          term: "accelerated — accéléré",
          definition:
            "Le temps avance plus vite. À ×30, environ 30 secondes de plateforme passent par seconde réelle ; calculs et actualisations prennent toujours du temps réel.",
        },
        {
          term: "manual — manuel",
          definition:
            "L’horloge attend une action explicite Avancer de 30 s. Vérifiez ce mode si le parcours semble figé.",
        },
        {
          term: "UTC et heure locale",
          definition:
            "UTC est un repère commun. L’heure locale dépend du fuseau du navigateur. Comparez les dates dans le même fuseau et distinguez date d’observation et dernière actualisation de l’API.",
        },
      ],
      action:
        "Dans Scénarios, consultez Horloge de plateforme. Gardez le temps réel pour la première panne ; accélérez à l’étape de rétablissement, puis revenez au temps réel.",
      result:
        "Le mode et le multiplicateur visibles expliquent l’évolution des graphiques et fenêtres de règles. Modifier l’horloge concerne toutes les personnes utilisant cette démo locale.",
      to: "/scenarios",
      view: "Examiner l’horloge de plateforme",
    },
    {
      id: "audit",
      title: "Admin : lire la piste d’audit",
      body: "Audit conserve les actions sensibles et tentatives refusées : qui a agi, quelle action, son résultat et sa date. Il ne remplace pas la chronologie d’incident et ne liste pas les alarmes de machines industrielles.",
      steps: [
        {
          instruction:
            "Avec un compte admin, ouvrez Audit. Choisissez des filtres d’action/résultat ou un intervalle UTC si nécessaire.",
          result:
            "La liste affiche les événements correspondants. Viewer/engineer n’a pas accès à cet écran.",
        },
        {
          instruction:
            "Lisez acteur, action, résultat et date d’un événement. Passez à la page suivante pour voir les résultats plus anciens.",
          result:
            "Vous distinguez une action autorisée d’un refus. Les codes techniques d’action restent identiques dans les deux langues.",
        },
      ],
      action:
        "Comparez une action effectuée à son entrée d’audit sans confondre temps simulé et temps réel.",
      result:
        "Audit utilise l’UTC de l’horloge réelle et survit à la réinitialisation. Les commentaires et preuves propres à un incident restent dans sa chronologie.",
      to: "/audit",
      view: "Ouvrir Audit (admin uniquement)",
    },
    {
      id: "standards",
      resources: [
        {
          href: "https://github.com/bachiryaye/iphi/blob/main/docs/industrial-references.md",
          label: "Références industrielles détaillées et sources (GitHub)",
        },
      ],
      title: "Les références industrielles de la conception",
      body: "Ces références ont guidé certains choix de conception. IPHI reste un démonstrateur indépendant et simulé, pas un produit industriel certifié. Voici ce que vous pouvez réellement montrer.",
      entries: [
        {
          term: "ISA-95 / IEC 62264 — responsabilités",
          definition:
            "Vocabulaire de la chaîne de données : source, passerelle, collecteur, historien et services consommateurs ont des rôles différents. Sept services ne signifient pas sept niveaux ISA-95.",
        },
        {
          term: "ISA-101 — IHM lisible",
          definition:
            "IHM signifie interface homme-machine : les écrans et commandes. IPHI garde une présentation sobre et distingue l’anormal par mots, formes et couleurs. La palette exacte d’IPHI est un choix de conception, pas une certification.",
        },
        {
          term: "ISA-18.2 / IEC 62682 — principes de gestion des alarmes",
          definition:
            "Expliquer les règles, confirmer les changements, éviter les doublons, prendre en compte et conserver l’historique. Les incidents IPHI concernent une plateforme, pas un système complet d’alarmes de sécurité du procédé.",
        },
        {
          term: "ISA/IEC 62443 — frontières et moindre privilège",
          definition:
            "OT désigne les technologies opérationnelles : équipements du site et leurs commandes. Les rôles sont contrôlés par le serveur ; aucune écriture OT ni réparation automatique n’est exécutée. La démo locale n’établit ni niveau de sécurité ni zones/conduits industriels validés.",
        },
        {
          term: "Qualité OPC UA — mesures utilisables",
          definition:
            "good, uncertain et bad décrivent la qualité des observations, distincte de la santé. Cette simplification en trois étiquettes n’est pas un connecteur OPC UA. Le transport optionnel réalisé est MQTT, avec des observations synthétiques.",
        },
      ],
      action:
        "Reliez un principe à un écran : formes d’état, confirmation de règle, incident unique malgré les répétitions ou restrictions viewer. Dans le dépôt, docs/industrial-references.md relie ces choix aux sources officielles, au code et aux tests.",
      result:
        "Vous expliquez les principes utilisés et leurs limites, sans annoncer une conformité complète, une compatibilité usine réelle ou une certification.",
    },
    {
      id: "presentation",
      resources: [
        {
          href: "https://github.com/bachiryaye/iphi#recorded-demonstration",
          label: "Voir la démonstration enregistrée (GitHub)",
        },
      ],
      title: "Présenter IPHI et vérifier ses acquis",
      body: "Utilisez le même parcours étayé pour votre entretien. Préparez une situation saine et un compte engineer avant de commencer. La durée dépend de la machine ; la vidéo de trois minutes contient des coupes et une récupération accélérée.",
      steps: [
        {
          instruction:
            "Expliquez le problème dans Vue d’ensemble : un service de données en panne peut rendre l’information industrielle indisponible ou ancienne. Annoncez que tous les équipements sont simulés.",
          result:
            "Votre interlocuteur comprend ce qu’IPHI surveille et ce qu’il ne prétend pas connecter.",
        },
        {
          instruction:
            "Lancez Arrêt du collecteur, ouvrez l’incident, suivez une règle et une preuve, puis demandez le diagnostic déterministe.",
          result:
            "Vous montrez le passage d’une observation à un état justifié puis à l’investigation, sans fournisseur IA obligatoire.",
        },
        {
          instruction:
            "Arrêtez le scénario, signalez toute accélération d’horloge, montrez le retour stable et exportez un rapport.",
          result:
            "Vous démontrez le cycle complet et la conservation des preuves. Expliquez que la supervision fonctionne sans LLM, que les hypothèses sont incertaines et qu’IPHI ne répare aucun équipement réel.",
        },
      ],
      entries: [
        {
          term: "Suis-je capable d’expliquer Inconnu ?",
          definition:
            "Oui : des preuves utilisables insuffisantes, jamais automatiquement Sain ni preuve d’un service arrêté.",
        },
        {
          term: "Suis-je capable de distinguer Prendre en compte et Arrêter ?",
          definition:
            "Prendre en compte enregistre la responsabilité ; Arrêter retire la panne simulée. Le retour attend encore des preuves stables.",
        },
        {
          term: "Puis-je étayer une conclusion affichée ?",
          definition:
            "Ouvrez sa version de règle et ses références d’observations/preuves. Distinguez faits, hypothèses et contrôles restant à faire.",
        },
      ],
      action:
        "Réalisez vous-même les six exercices une fois. Si une réponse manque, revenez au sujet du guide avant de présenter.",
      result:
        "Vous pouvez démontrer l’outil et expliquer ses limites. Le README du dépôt contient la vidéo native GitHub, sa transcription, l’installation et le guide détaillé des références industrielles.",
    },
  ],
};
