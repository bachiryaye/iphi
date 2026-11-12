# ADR 0007 — Sécurité avant et après US-11

- **Statut :** Acceptée
- **Date :** 2026-11-12
- **Portée :** dossier de conception v1.1

## Contexte

US-11 (authentification, RBAC) est P1, mais la démo P0 expose des mutations (scénarios, ack, resolve). Le scénario obligatoire 7 (viewer refusé) dépend de US-11.

## Décision

- Avant US-11 : mutations actives seulement si `IPHI_DEV_MUTATIONS=true` et API liée à `127.0.0.1` ; sinon `403 MUTATIONS_DISABLED`. Acteur `dev-local`, mutations auditées. Bannière d'interface explicite.
- US-11 : sessions serveur en cookie `HttpOnly`/`SameSite=Strict` (`Secure` hors dev), jeton anti-CSRF sur mutations, Argon2id, rôles appliqués par dépendance FastAPI, utilisateurs de démo créés au seed avec mots de passe issus de l'environnement.
- Dès US-01 : secrets hors Git, `.env.example` factice, gitleaks en CI, ports locaux, CORS restreint, en-têtes de sécurité, corps de requête bornés.
- Scénario obligatoire 7 exigible à partir de US-11.

## Alternatives écartées

- JWT en `localStorage` : exposé au XSS, révocation complexe.
- Fournisseur d'identité externe (OIDC) : dépendance externe inutile pour une démo locale.
- Avancer US-11 en P0 : retarde la démo sans bénéfice de démonstration équivalent.

## Conséquences

- Le mode dev est documenté comme non sûr hors poste local.
- Passage à US-11 sans modifier les routes : seule la dépendance d'autorisation change.
