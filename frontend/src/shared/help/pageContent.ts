import type { HelpTopic } from "./content";

export interface PageGuidance {
  topic: HelpTopic;
  en: string;
  fr: string;
}
export const pageGuidance = {
  login: {
    topic: "start",
    en: "Use a local account from the demo owner. Viewer can read and export; engineer can investigate and run scenarios; admin can also reset and read Audit. Open the beginner guide before signing in.",
    fr: "Utilisez un compte local fourni par le propriétaire. Viewer peut consulter et exporter ; engineer peut investiguer et lancer des scénarios ; admin peut aussi réinitialiser et consulter Audit. Le guide débutant est accessible avant connexion.",
  },
  overview: {
    topic: "states",
    en: "Read the platform state with its deciding rule, then compare the components and active incidents. Monitor status describes IPHI itself. Open a component or incident for evidence; scenario actions require engineer/admin.",
    fr: "Lisez l’état global et sa règle décisive, puis comparez les composants et incidents actifs. L’état du moniteur décrit IPHI lui-même. Ouvrez un composant ou incident pour les preuves ; les scénarios exigent engineer/admin.",
  },
  topology: {
    topic: "tour",
    en: "Arrows follow data from a dependency to its dependent. Select a node to inspect it; use the table for keyboard navigation. Impact annotates dependency relationships without changing the server’s component state. All roles can inspect.",
    fr: "Les flèches suivent les données d’une dépendance vers le composant qui en dépend. Sélectionnez un nœud ; le tableau permet aussi la navigation clavier. L’impact annote les dépendances sans changer l’état propre calculé par le serveur. Tous les rôles peuvent consulter.",
  },
  components: {
    topic: "metrics",
    en: "Filter the seven simulated components by state, type or criticality, then open a row for metrics, logs and rules. Unknown means insufficient evidence. All roles can inspect; no action here changes the monitored service.",
    fr: "Filtrez les sept composants simulés par état, type ou criticité, puis ouvrez une ligne pour les métriques, journaux et règles. Inconnu signifie que les preuves sont insuffisantes. Tous les rôles peuvent consulter ; aucune action ici ne modifie le service supervisé.",
  },
  component: {
    topic: "metrics",
    en: "Compare stored health evaluations with metric history and warning/error logs. Select a time or evidence chip to inspect a proof. A gap means missing samples; a rule may combine several measurements over a period. All roles can inspect. Stored explanations and logs keep their original language.",
    fr: "Comparez les évaluations enregistrées à l’historique des métriques et aux journaux d’avertissement/erreur. Sélectionnez un instant ou une citation pour la preuve. Un trou indique des mesures absentes ; une règle peut combiner plusieurs mesures sur une période. Tous les rôles peuvent consulter. Explications et journaux gardent leur langue d’origine.",
  },
  incidents: {
    topic: "incidents",
    en: "Filter by severity, status, component or failure class and open an incident. Occurrences group repeated signals; acknowledgement does not clear the fault. All roles can read and export; engineer/admin can change incidents and diagnose.",
    fr: "Filtrez par gravité, statut, composant ou classe et ouvrez un incident. Les occurrences regroupent les signaux répétés ; prendre en compte ne supprime pas la panne. Tous les rôles peuvent lire et exporter ; engineer/admin peut modifier et diagnostiquer.",
  },
  incident: {
    topic: "incidents",
    en: "Follow Signal → Timeline → Evidence chain. Engineer/admin can acknowledge, comment and diagnose; resolution waits for the active condition to clear. All roles can export PDF/CSV. Facts, hypotheses and checks are distinct. Stored evidence and generated text remain in their original language; reports remain English.",
    fr: "Suivez Signal → Chronologie → Chaîne de preuves. Engineer/admin peut prendre en compte, commenter et diagnostiquer ; la résolution attend le rétablissement. Tous les rôles peuvent exporter PDF/CSV. Faits, hypothèses et vérifications sont distincts. Preuves et textes produits gardent leur langue d’origine ; les rapports restent en anglais.",
  },
  scenarios: {
    topic: "scenarios",
    en: "Choose a catalog fault and target; engineer/admin can start or stop runs and change the platform clock. Empty duration means until stopped. Watch Overview, investigate its incident, then Stop to observe recovery. Reset requires admin, clears simulated observations and preserves incident evidence.",
    fr: "Choisissez une panne du catalogue et sa cible ; engineer/admin peut démarrer, arrêter et changer l’horloge. Une durée vide signifie jusqu’à l’arrêt. Consultez Vue d’ensemble, examinez l’incident, puis Arrêter pour observer le rétablissement. Réinitialiser exige admin, efface les observations simulées et conserve les preuves d’incident.",
  },
  rules: {
    topic: "rules",
    en: "Read the version, metric, aggregation window, thresholds and raise/clear confirmation counts. These are demonstration values. Unknown does not pass a rule. All roles can read; rules cannot be edited here. Stored rationale and recommendations retain their original language.",
    fr: "Lisez version, métrique, fenêtre d’agrégation, seuils et nombres de confirmations de déclenchement/rétablissement. Ce sont des valeurs de démonstration. Inconnu ne valide pas une règle. Tous les rôles peuvent lire ; aucune édition ici. Les justifications et recommandations enregistrées gardent leur langue d’origine.",
  },
  audit: {
    topic: "audit",
    en: "Admin only: inspect sensitive actions and denied attempts, filter by action/outcome and UTC interval, then page through results. Audit uses real wall-clock UTC rather than simulated platform time. Reset preserves this journal. Technical action codes and details keep their original values.",
    fr: "Admin uniquement : consultez les actions sensibles et tentatives refusées, filtrez par action/résultat et intervalle UTC, puis parcourez les pages. Audit utilise l’UTC réel, distinct du temps simulé. Réinitialiser conserve ce journal. Les codes d’action et détails techniques gardent leurs valeurs d’origine.",
  },
  notfound: {
    topic: "start",
    en: "This address is unavailable. Return to Overview or use the beginner guide to find a supported page. Sign in if your session has expired.",
    fr: "Cette adresse est indisponible. Revenez à Vue d’ensemble ou utilisez le guide débutant pour trouver une page. Reconnectez-vous si la session a expiré.",
  },
} satisfies Record<string, PageGuidance>;
export type HelpPageKey = keyof typeof pageGuidance;

export function pageForPath(path: string): HelpPageKey {
  if (path === "/") return "overview";
  if (path.startsWith("/components/")) return "component";
  if (path.startsWith("/incidents/")) return "incident";
  return (
    Object.keys(pageGuidance).find((key): key is HelpPageKey => key === path.slice(1)) ?? "notfound"
  );
}
