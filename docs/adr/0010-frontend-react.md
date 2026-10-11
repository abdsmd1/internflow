# 0010 — Frontend React typé par le contrat OpenAPI

- **Statut :** Accepté
- **Date :** 2026-10-11

## Contexte

Jusqu'ici, InternFlow ne s'utilisait qu'à travers Swagger. Les RH, les encadrants
et les stagiaires ont besoin d'une interface : suivre les stages, confier et faire
avancer les tâches, déposer et relire les rapports hebdomadaires.

Deux risques sont propres à un frontend séparé de l'API : que les deux divergent
(un champ renommé côté API casse l'interface sans prévenir), et que la sécurité
repose sur l'interface au lieu de l'API.

## Décision

### Pile technique

- **React 19 + TypeScript strict + Vite** dans `frontend/`.
- **React Router** pour la navigation, **TanStack Query** pour le cache, les
  états de chargement et le rafraîchissement après une modification.
- Aucune bibliothèque de composants : du HTML sémantique et une feuille de style
  avec des variables CSS (thème clair et sombre, police Atkinson Hyperlegible
  hébergée avec l'application).

### Un seul contrat : OpenAPI

```
code FastAPI ──export──► services/api/openapi.json ──openapi-typescript──► src/api/schema.d.ts
```

- Le contrat est **commité**. Un test de l'API échoue s'il ne correspond plus au
  code ; la CI du frontend échoue si les types TypeScript ne correspondent plus au
  contrat. `make openapi` régénère les deux.
- Les appels passent par **openapi-fetch** : URL, paramètres et corps sont vérifiés
  à la compilation. Une route renommée devient une erreur TypeScript, pas un bug
  découvert en production.

### Sécurité

- **L'API reste seule juge.** L'interface masque les boutons qu'un rôle ne peut pas
  utiliser, par confort ; les refus de l'API (403, 404, 409) sont affichés tels quels.
- **Même origine** : nginx sert les fichiers et relaie `/api` vers l'API (Vite fait de
  même en développement). Pas de CORS à ouvrir.
- **En-têtes stricts** : `Content-Security-Policy` sans script ni style externe ou
  en ligne, `frame-ancestors 'none'`, `nosniff`, `no-referrer`.
- **Jeton en `sessionStorage`** : il disparaît à la fermeture de l'onglet. Un 401 de
  l'API efface la session et ramène à la connexion. À la déconnexion, tout le cache
  est vidé pour qu'aucune donnée ne passe d'un utilisateur à l'autre.
- Image **Alpine + nginx sans root**, système de fichiers en lecture seule dans Compose.
  Le paquet nginx d'Alpine est préféré à l'image officielle `nginx-unprivileged:1.28` :
  le scan Trivy y a trouvé 10 failles (dont une critique) déjà corrigées chez Alpine.

### Qualité

- **Vitest + Testing Library** : les tests manipulent l'interface comme un
  utilisateur (libellés, rôles ARIA), jamais les détails d'implémentation.
- **MSW** simule l'API au niveau HTTP, avec les vraies URL et le format d'erreur
  RFC 9457 : le client réel est testé, pas un faux.
- ESLint (`strictTypeChecked`), Prettier, couverture minimale de 80 %.

## Alternatives envisagées

- **Jeton dans un cookie `HttpOnly`** : inaccessible au JavaScript, donc plus robuste
  face au XSS, mais il faut ajouter une protection CSRF et modifier l'API. Retenu
  comme amélioration future ; la CSP stricte limite le risque en attendant.
- **Next.js** : rendu serveur inutile pour une application interne derrière une
  connexion ; une application monopage statique est plus simple à déployer.
- **Types écrits à la main** : rapides au début, mais ils divergent de l'API sans
  que rien ne le signale.
- **Bibliothèque de composants (MUI, Ant Design)** : gain de temps, mais une
  interface générique et un poids important pour une dizaine d'écrans.

## Conséquences

- ✅ Une modification de l'API qui casse l'interface est détectée en CI.
- ✅ Les trois rôles disposent de leurs écrans ; la frise des semaines montre d'un
  coup d'œil la régularité des rapports hebdomadaires.
- ⚠️ Les noms des stagiaires et encadrants sont chargés un par un (mis en cache) :
  acceptable à cette échelle ; un champ résumé dans `InternshipRead` serait plus
  efficace pour de longues listes.
- ⚠️ Pas encore de test de bout en bout dans un vrai navigateur contre la vraie API
  (Playwright) : à ajouter quand les parcours se stabiliseront.
