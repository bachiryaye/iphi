# ADR 0006 — Contrat de diagnostic, diagnostic déterministe et adaptateur LLM

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

Deux formats de sortie coexistaient (architecture v1.0 plat, contrat d'ingénierie imbriqué). US-10 (P0) exige « diagnostiquer » alors que US-08 (IA) est P1. Le LLM ne doit jamais être une condition de fonctionnement.

## Décision

- Format unique : le format imbriqué, repris dans l'architecture §06.1 (preuves par affirmation, incertitude par hypothèse, `limitations`, `model`). Table `diagnostic` alignée.
- Diagnostic **déterministe** au même format, livré en US-05 : faits issus des évaluations déclenchantes, hypothèse = composant défaillant le plus en amont (corrélation, non causalité), vérifications = recommandations des règles.
- Adaptateur LLM (US-08) : `none` (défaut), `fake` (tests), fournisseur configuré par variables d'environnement. Paquet de preuves borné, identifiants courts `E1…En`, logs encapsulés comme données non fiables, masquage des secrets, timeout 20 s, 1 nouvelle tentative, plafonds de tokens, aucun outil exposé.
- Validation stricte : preuve inconnue ⇒ affirmation retirée et signalée ; sortie invalide ⇒ `rejected` + fallback déterministe.
- Prompt persisté **masqué** uniquement ; jamais journalisé brut.

## Alternatives écartées

- Diagnostic uniquement par LLM : démo dépendante d'une clé, d'un coût et d'un réseau.
- Format plat v1.0 : impossible de vérifier quelle preuve soutient quelle affirmation.

## Conséquences

- La démo P0 fonctionne sans clé ni coût.
- Le choix du fournisseur et du modèle par défaut est reporté à US-08 (configuration, pas code).
