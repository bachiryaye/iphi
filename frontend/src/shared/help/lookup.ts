import type { HelpSection } from "./content";

export const lookup: Record<"en" | "fr", readonly HelpSection[]> = {
  en: [
    {
      id: "glossary",
      title: "Vocabulary, units and time",
      body: "You can use the tool before knowing these words. Return to this reference whenever a term is unfamiliar.",
      action:
        "Find the term or symptom that matches your question, then return to the exercise using the contents.",
      result:
        "If a problem persists, tell the owner the page, action, time and displayed correlation ID. Keep passwords and session data private.",
      entries: [
        {
          term: "Platform / component",
          definition:
            "The whole monitored data chain / one service in that chain. The simulated chain includes source, gateway, collector, historian, database, API and analytics.",
        },
        {
          term: "Gateway / collector / historian",
          definition:
            "A gateway bridges data paths; a collector gathers observations; a historian keeps time-stamped process history. These are simulated responsibilities in IPHI.",
        },
        {
          term: "Metric / sample / telemetry",
          definition:
            "A named quantity such as latency / one value at one time / the collected measurements and logs. Example: probe_latency_ms = 25 at a recorded UTC time.",
        },
        {
          term: "Probe / availability / latency",
          definition:
            "An active check / whether the service answers / how long that answer takes. A fast reply does not prove process data is fresh.",
        },
        {
          term: "Freshness / data_age_s",
          definition:
            "How old the process data is. Example: data_age_s = 120 means two minutes old, even if the service is reachable.",
        },
        {
          term: "Rule / evaluation / evidence",
          definition:
            "An explicit test / the recorded result of applying that test / the observations and evaluations used to justify a conclusion.",
        },
        {
          term: "Window / aggregate",
          definition:
            "The time interval being examined / a calculation over its values, such as an average or ratio. A threshold may apply to this result rather than one sample.",
        },
        {
          term: "Confirmation / hysteresis",
          definition:
            "Require repeated evaluations before changing state / require stable recovery and separate clear thresholds to avoid rapid state oscillation.",
        },
        {
          term: "Fingerprint / occurrence / deduplication",
          definition:
            "A stable grouping key / a repeated signal / grouping those repeats into one active incident instead of creating duplicates.",
        },
        {
          term: "Dependency / downstream impact",
          definition:
            "A service relies on another / a problem can affect services consuming its data. Impact annotations do not replace a component’s own health.",
        },
        {
          term: "ms / s / % / count",
          definition:
            "Milliseconds / seconds / percent / a quantity. 1,000 ms = 1 s; 300 s = 5 minutes. Always read the unit beside the value.",
        },
        {
          term: "UTC / observation time / update age",
          definition:
            "Shared timezone reference / when the measurement happened / how old the interface’s latest API response is. These are not interchangeable.",
        },
        {
          term: "MQTT / OPC UA / LLM",
          definition:
            "An optional message transport implemented here with synthetic data / the source of IPHI’s quality vocabulary, without an OPC UA adapter / an optional language model for explanations, never the health authority.",
        },
      ],
    },
    {
      id: "troubleshooting",
      title: "When something looks wrong",
      body: "Find the symptom, try the suggested check and read the result before repeating an action. If you need the demo owner’s help, share the page, action, time and correlation ID; keep passwords and session data private.",
      action:
        "Find the term or symptom that matches your question, then return to the exercise using the contents.",
      result:
        "If a problem persists, tell the owner the page, action, time and displayed correlation ID. Keep passwords and session data private.",
      entries: [
        {
          term: "No account or sign-in fails",
          definition:
            "Ask the owner for the correct local username/password. Check typing, then try once. There is no registration or self-service password reset. A 401 later usually means you must sign in again.",
        },
        {
          term: "Button greyed out / 403",
          definition:
            "Read your role and the on-screen reason. Viewer cannot change scenarios or diagnose; Audit and Reset require admin. Ask for an authorized account, rather than repeatedly clicking.",
        },
        {
          term: "Unknown just after startup",
          definition:
            "Allow collection and rule windows to fill. Check the monitor and sample times. If no recent observations arrive, this is missing evidence: do not label it Healthy.",
        },
        {
          term: "No incident after starting the fault",
          definition:
            "Check the active collector_down run, collector-01 target, clock mode and monitor. Remove incident filters. Realtime targets 15 s but a loaded host may take longer; do not start duplicate faults.",
        },
        {
          term: "Graph empty or values look frozen",
          definition:
            "Check the selected time window, platform time and manual clock mode. A stale-view or connection warning means refreshes failed. Retry the failed view; do not treat old values as fresh evidence.",
        },
        {
          term: "No recent warning/error logs",
          definition:
            "The log panel intentionally shows warning/error records, not every successful action. An empty panel can be normal. Compare metrics and evaluations before concluding that collection failed.",
        },
        {
          term: "Incident stays active after Stop",
          definition:
            "Check that the correct run stopped and no other fault remains. Wait for rule windows and stable recovery; connectivity uses 300 platform seconds. Acknowledge does not clear a fault.",
        },
        {
          term: "AI off or unavailable",
          definition:
            "Use Diagnose for the deterministic version. AI diagnosis requires optional configuration; monitoring, incidents and exports do not require it. Do not enter a provider key into a comment.",
        },
        {
          term: "No downloaded report / export refused",
          definition:
            "Check browser Downloads, then the displayed error. Retry a busy renderer later. Oversized reports are refused explicitly; use on-screen evidence/timeline to continue the investigation.",
        },
        {
          term: "429 / API error / monitor stalled",
          definition:
            "Wait if rate-limited, then retry. For a persistent API or monitor error, send its correlation ID and time to the demo owner. The owner can inspect readiness/logs; a novice need not edit configuration or restart services blindly.",
        },
        {
          term: "French interface but English evidence",
          definition:
            "Expected: stored logs, comments, diagnoses and technical keys retain their language. PDF/CSV remain English. The language switch changes interface text, not recorded evidence.",
        },
      ],
    },
  ],
  fr: [
    {
      id: "glossary",
      title: "Vocabulaire, unités et temps",
      body: "Vous pouvez utiliser l’outil avant de connaître ces mots. Revenez ici chaque fois qu’un terme vous semble nouveau.",
      action:
        "Choisissez le terme ou le symptôme qui correspond à votre question. Revenez ensuite à l’exercice avec le sommaire.",
      result:
        "Si le blocage persiste, indiquez au propriétaire la page, l’action, l’heure et l’identifiant de corrélation affiché. Gardez les mots de passe et données de session privés.",
      entries: [
        {
          term: "Plateforme / composant",
          definition:
            "Toute la chaîne supervisée / un service de cette chaîne. La chaîne simulée comprend source, passerelle, collecteur, historien, base, API et analyse.",
        },
        {
          term: "Passerelle / collecteur / historien",
          definition:
            "La passerelle relie des chemins de données ; le collecteur rassemble les observations ; l’historien conserve l’historique daté du procédé. Ce sont des responsabilités simulées dans IPHI.",
        },
        {
          term: "Métrique / échantillon / télémétrie",
          definition:
            "Une grandeur nommée, comme la latence / une valeur à un instant / l’ensemble des mesures et journaux collectés. Exemple : probe_latency_ms = 25 à une date UTC enregistrée.",
        },
        {
          term: "Sonde / disponibilité / latence",
          definition:
            "Une vérification active / le fait qu’un service répond / le temps nécessaire pour répondre. Une réponse rapide ne prouve pas la fraîcheur des données du procédé.",
        },
        {
          term: "Fraîcheur / data_age_s",
          definition:
            "L’âge des données du procédé. Exemple : data_age_s = 120 signifie deux minutes, même si le service reste joignable.",
        },
        {
          term: "Règle / évaluation / preuve",
          definition:
            "Un test explicite / le résultat enregistré de ce test / les observations et évaluations qui justifient une conclusion.",
        },
        {
          term: "Fenêtre / agrégat",
          definition:
            "La période examinée / un calcul sur ses valeurs, par exemple une moyenne ou une proportion. Le seuil peut concerner ce résultat et non un échantillon isolé.",
        },
        {
          term: "Confirmation / hystérésis",
          definition:
            "Attendre plusieurs évaluations avant de changer d’état / exiger un retour stable et des seuils de rétablissement distincts pour éviter les oscillations rapides.",
        },
        {
          term: "Empreinte / occurrence / déduplication",
          definition:
            "Une clé stable de regroupement / un signal répété / le regroupement de ces répétitions dans un incident actif au lieu de créer des doublons.",
        },
        {
          term: "Dépendance / impact en aval",
          definition:
            "Un service en utilise un autre / un problème peut affecter les services qui consomment ses données. L’impact ne remplace pas la santé propre d’un composant.",
        },
        {
          term: "ms / s / % / count",
          definition:
            "Millisecondes / secondes / pourcentage / une quantité. 1 000 ms = 1 s ; 300 s = 5 minutes. Lisez toujours l’unité à côté de la valeur.",
        },
        {
          term: "UTC / date d’observation / âge d’actualisation",
          definition:
            "Un fuseau de référence commun / quand la mesure a eu lieu / l’âge de la dernière réponse API reçue par l’interface. Ces informations ne sont pas interchangeables.",
        },
        {
          term: "MQTT / OPC UA / LLM",
          definition:
            "Un transport de messages optionnel réalisé ici avec des données synthétiques / l’origine du vocabulaire de qualité d’IPHI, sans connecteur OPC UA / un modèle de langage facultatif pour expliquer, jamais pour décider de la santé.",
        },
      ],
    },
    {
      id: "troubleshooting",
      title: "Si quelque chose semble incorrect",
      body: "Retrouvez le symptôme, essayez le contrôle proposé et lisez le résultat avant de recommencer une action. Pour demander de l’aide au propriétaire, indiquez page, action, date et identifiant de corrélation ; gardez mots de passe et données de session privés.",
      action:
        "Choisissez le terme ou le symptôme qui correspond à votre question. Revenez ensuite à l’exercice avec le sommaire.",
      result:
        "Si le blocage persiste, indiquez au propriétaire la page, l’action, l’heure et l’identifiant de corrélation affiché. Gardez les mots de passe et données de session privés.",
      entries: [
        {
          term: "Pas de compte ou connexion refusée",
          definition:
            "Demandez au propriétaire les bons identifiants locaux. Vérifiez la saisie, puis réessayez une fois. Il n’y a ni inscription ni réinitialisation de mot de passe en libre-service. Un 401 ultérieur signifie généralement qu’il faut se reconnecter.",
        },
        {
          term: "Bouton grisé / 403",
          definition:
            "Lisez votre rôle et la raison affichée. Viewer ne peut ni changer les scénarios ni diagnostiquer ; Audit et Réinitialiser exigent admin. Demandez un compte autorisé au lieu de cliquer plusieurs fois.",
        },
        {
          term: "Inconnu juste après le démarrage",
          definition:
            "Laissez la collecte et les fenêtres de règles se remplir. Vérifiez le moniteur et les dates des mesures. Sans observation récente, les preuves manquent : ne concluez pas Sain.",
        },
        {
          term: "Aucun incident après le lancement de la panne",
          definition:
            "Vérifiez l’exécution active collector_down, la cible collector-01, le mode d’horloge et le moniteur. Retirez les filtres d’incidents. L’objectif est de 15 s en temps réel, davantage sur machine chargée ; ne relancez pas de doublons.",
        },
        {
          term: "Graphique vide ou valeurs figées",
          definition:
            "Vérifiez la période choisie, l’heure de plateforme et le mode manuel. Une vue périmée ou une alerte de connexion indique des actualisations en échec. Réessayez la vue ; une ancienne valeur n’est pas une preuve récente.",
        },
        {
          term: "Aucun journal récent d’avertissement/erreur",
          definition:
            "Ce panneau montre volontairement les avertissements/erreurs, pas toutes les actions réussies. Il peut donc être vide normalement. Comparez mesures et évaluations avant de conclure à une panne de collecte.",
        },
        {
          term: "L’incident reste actif après Arrêter",
          definition:
            "Vérifiez que la bonne exécution est arrêtée et qu’aucune autre panne ne reste. Attendez les fenêtres et un retour stable ; la connectivité utilise 300 secondes de plateforme. Prendre en compte ne supprime pas une panne.",
        },
        {
          term: "IA désactivée ou indisponible",
          definition:
            "Utilisez Diagnostiquer pour la version déterministe. Diagnostic IA nécessite une configuration facultative ; supervision, incidents et exports n’en dépendent pas. Ne saisissez pas de clé fournisseur dans un commentaire.",
        },
        {
          term: "Rapport introuvable / export refusé",
          definition:
            "Consultez les Téléchargements du navigateur, puis l’erreur affichée. Réessayez plus tard si le moteur est occupé. Un rapport trop volumineux est refusé explicitement ; poursuivez avec les preuves et la chronologie à l’écran.",
        },
        {
          term: "429 / erreur API / moniteur bloqué",
          definition:
            "Patientez en cas de limitation, puis réessayez. Si une erreur API ou du moniteur persiste, transmettez l’identifiant de corrélation et l’heure au propriétaire. Il peut consulter disponibilité/journaux ; un débutant n’a pas à modifier la configuration ni redémarrer au hasard.",
        },
        {
          term: "Interface française mais preuves anglaises",
          definition:
            "C’est attendu : journaux, commentaires, diagnostics enregistrés et clés techniques gardent leur langue. Les PDF/CSV restent en anglais. Le sélecteur traduit l’interface, pas les preuves stockées.",
        },
      ],
    },
  ],
};
