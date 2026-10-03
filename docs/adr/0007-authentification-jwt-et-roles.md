# 0007 — Authentification par jeton JWT et contrôle d'accès par rôles

- **Statut :** Accepté
- **Date :** 2026-10-03

## Contexte

L'API manipule des données personnelles (stagiaires, évaluations à venir). Chaque
requête doit être attribuée à une personne, et chaque personne ne doit voir et
modifier que ce que son rôle autorise. L'agent IA (phase 4) sera lui aussi un
appelant, avec des droits limités.

## Décision

### Authentification

- **Flux OAuth2 « password »** : `POST /api/v1/auth/token` (e-mail + mot de passe)
  renvoie un **jeton d'accès JWT** à utiliser dans `Authorization: Bearer …`.
  Ce flux active le bouton *Authorize* de Swagger UI.
- **Mots de passe hachés avec Argon2id** (recommandation OWASP) : sel aléatoire,
  jamais stockés ni renvoyés en clair. Politique : 12 à 128 caractères (NIST
  SP 800-63B privilégie la longueur), sans l'identifiant de l'e-mail.
- **Erreur unique** « E-mail ou mot de passe incorrect » et **temps de réponse
  constant** (vérification factice si le compte n'existe pas) : on ne révèle pas
  quels e-mails sont enregistrés.
- **JWT HS256** signé avec un secret d'au moins 32 caractères, **sans valeur par
  défaut** (l'API refuse de démarrer sans lui). Au décodage : algorithme imposé
  (pas de `alg: none`), émetteur et audience vérifiés, expiration courte (30 min).
- **Premier compte RH** créé par une commande d'administration
  (`python -m internflow_api.cli create-hr-user`) : aucun compte par défaut.

### Autorisation

- Trois rôles : `hr`, `supervisor`, `intern`. Un compte encadrant ou stagiaire est
  lié à **son** profil métier (au plus un compte par profil, contrainte `UNIQUE`).
- Les règles sont dans le **domaine** (`domain/authorization.py`) et appliquées
  **dans chaque cas d'usage**, qui reçoit l'identité de l'appelant (`actor`) :
  la protection ne dépend pas de la couche HTTP et s'appliquera aussi à l'agent IA.
- Une ressource que l'appelant ne peut pas **voir** répond **404** (son existence
  n'est pas révélée) ; une action refusée sur une ressource visible répond **403**.

| Action | RH | Encadrant | Stagiaire |
|---|---|---|---|
| Créer stagiaires, encadrants, stages, comptes | ✅ | ❌ | ❌ |
| Consulter les stagiaires | ✅ | ✅ | lui-même |
| Consulter les encadrants | ✅ | ✅ | ✅ |
| Consulter les stages | ✅ | les siens | les siens |
| Démarrer / terminer un stage | ✅ | les siens | ❌ |
| Annuler un stage | ✅ | ❌ | ❌ |

## Alternatives envisagées

- **Sessions côté serveur (cookie)** : révocation immédiate, mais état partagé à
  gérer et moins adapté à un client API (agent IA, frontend séparé).
- **Fournisseur d'identité externe (Keycloak, Auth0)** : idéal en entreprise
  (SSO, MFA), mais une infrastructure de plus ; le port `TokenService` permettra
  de migrer sans toucher aux cas d'usage.
- **RS256 (clé asymétrique)** : utile quand plusieurs services vérifient les
  jetons sans pouvoir en émettre. À reconsidérer lorsque l'agent IA sera un
  service séparé.
- **Contrôles uniquement dans les routes** : plus simple, mais un nouveau point
  d'entrée (agent IA, tâche planifiée) pourrait les contourner.

## Conséquences

- ✅ Chaque règle d'accès est testée unitairement et de bout en bout, rôle par rôle.
- ⚠️ Un jeton reste valide jusqu'à son expiration, même si le compte est désactivé
  ou change de rôle (d'où la durée courte). Évolutions prévues : jeton de
  rafraîchissement, liste de révocation (le `jti` est déjà présent), limitation
  du nombre de tentatives de connexion.
