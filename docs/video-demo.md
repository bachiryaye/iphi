# Recorded demonstration — French, three minutes

[Download / play the MP4](media/iphi-demo-fr.mp4) · [French text track](media/iphi-demo-fr.vtt) · [Recording and edit sources](media/README.md)

This is an edited recording of the actual IPHI browser interface, with French explanatory panels and no audio. It follows one simulated collector failure through metrics, evidence, deterministic diagnosis, a real CSV download and recovery. It ends with the public English/French guide. No terminal, login form, password or session token is recorded.

Application source: `83b87b3` (the delivered application on `main`). Recorded on 19 November 2026 against a separate, seeded local Compose project, with the AI provider set to `none`. Remotion renders the explanatory panels; FFmpeg combines them with the browser footage. No observation, chart, status or diagnostic text was replaced.

**Editing and time:** the eight chapters retain their chronological order. Pauses, loading and waiting periods are cut; the film is not a continuous three-minute runtime or a detection-performance measurement. The platform clock is changed to ×30 during recovery, as shown in the interface. The monitor, stored evidence and simulation limitations remain those of the application.

**Scope:** this recording illustrates the collector investigation journey. Freshness, missing telemetry, latency, MQTT, PDF reporting and role enforcement have their separate checked paths in the [demo guide](demo.md), [MQTT guide](mqtt.md) and [access guide](access.md). MQTT uses a real local broker with synthetic observations; no real plant is connected.

## French transcript

The following text describes the visible actions and reproduces the explanatory panels. The downloadable WebVTT track provides the same chapter descriptions for a media player.

### 00:00 — Comprendre la plateforme

La vue d’ensemble affiche sept composants sains et un moniteur actif.

IPHI surveille sept composants simulés : source, passerelle, collecteur, historisation, base de données, API et analyse. La santé de la plateforme et celle du moniteur sont distinctes.

Captures réelles de l’application. Aucun équipement industriel connecté.

### 00:18 — Provoquer une panne

Le catalogue est ouvert et le scénario collector_down est démarré sur collector-01.

Un scénario arrête les réponses du collecteur. Le catalogue annonce le résultat attendu. Les rôles engineer et admin peuvent agir ; viewer peut consulter.

Le scénario modifie uniquement les données de la simulation.

### 00:36 — Expliquer l’état critique

La vue d’ensemble montre collector-01 critique et un seul incident actif.

Le collecteur devient Critique après confirmation par les règles. Un incident regroupe les signaux répétés et décrit les dépendances affectées. L’état global suit une priorité explicite.

Inconnu signifie preuves insuffisantes, jamais Sain par défaut.

### 00:54 — Relier mesures et règles

La fiche collector-01 montre le graphique de disponibilité, la bande d’états et les lignes de règles.

La fiche composant réunit les métriques avec leurs unités et les évaluations enregistrées. Chaque règle expose sa fenêtre, son seuil et les preuves expliquant son résultat.

Les graphiques montrent les échantillons réellement stockés.

### 01:14 — Retrouver les preuves

La page INC-0001 montre le signal puis les évaluations et les échantillons de sa chaîne de preuves.

L’incident conserve son signal, sa chronologie et sa chaîne de preuves. Les références permettent de retrouver les évaluations, journaux et mesures qui étayent l’investigation.

Prendre en compte un incident ne répare pas la panne.

### 01:34 — Diagnostiquer et exporter

Le diagnostic est demandé. Les faits et leurs citations sont affichés, une preuve est sélectionnée, puis Exporter CSV déclenche le téléchargement du rapport.

Le diagnostic déterministe sépare faits, hypothèse, vérifications et limites. Il fonctionne sans fournisseur IA. L’export CSV reprend les preuves enregistrées et signale leur origine simulée.

Les preuves gardent leur langue d’origine. Les exports restent anglais.

### 02:10 — Observer le rétablissement

Le scénario collector_down est arrêté, la vitesse est réglée sur 30, puis Accélérer est choisi. Après une coupe d’attente, l’incident affiche Résolu et la plateforme est saine.

Le scénario est arrêté puis l’horloge de plateforme accélérée à ×30. L’incident se résout après une période stable. Les preuves et l’historique restent consultables.

Temps simulé accéléré visible dans l’interface. Coupes de montage signalées dans la transcription.

### 02:38 — Continuer avec l’aide

La page Aide est ouverte, le sélecteur passe à English puis à Français. La page rechargée conserve le français.

L’aide publique détaille les étapes, les résultats attendus, les rôles et le dépannage. Le sélecteur Français / English traduit l’interface et conserve le choix après rechargement.

Démonstrateur local : aucune remédiation ni validation en usine réelle.
