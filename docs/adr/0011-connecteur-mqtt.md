# ADR 0011 — US-12 : MQTT plutôt qu'OPC UA

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

US-12 demande un seul adaptateur, MQTT ou OPC UA, avec serveur simulé.

## Décision

- MQTT : broker Mosquitto (profil Compose `mqtt`), publieur simulé, client `paho-mqtt` dans le worker via l'interface `Connector`, topics `iphi/<platform>/<component>/metrics` et `/logs`, payload JSON versionné et validé (Pydantic).
- Données étiquetées `source=mqtt`, environnement toujours `simulation`.
- Sparkplug B hors V1 (évolution documentée).

## Alternatives écartées

- OPC UA (`asyncua`) : plus représentatif des automates mais modèle d'information, sécurité et certificats bien plus lourds pour une extension P2.

## Conséquences

- Démontre l'indépendance du moteur vis-à-vis de la source.
- Aucune prétention de compatibilité avec un produit industriel réel.
