# internflow-web

Interface web d'InternFlow : React 19, TypeScript strict, Vite. Les choix sont
expliqués dans l'[ADR 0010](../docs/adr/0010-frontend-react.md).

## Démarrer

Avec Docker (depuis la racine du dépôt) : `docker compose up --build -d`, puis
http://localhost:8080.

En développement, avec rechargement instantané (l'API doit tourner sur le port 8000) :

```bash
npm install
npm run dev        # http://localhost:5173, /api est relayé vers l'API
```

## Commandes

| Commande            | Rôle                                                              |
| ------------------- | ----------------------------------------------------------------- |
| `npm run lint`      | ESLint + vérification Prettier                                    |
| `npm run typecheck` | TypeScript strict                                                 |
| `npm test`          | Tests (Vitest + Testing Library + MSW) avec couverture            |
| `npm run build`     | Fichiers de production dans `dist/`                               |
| `npm run gen:api`   | Régénère `src/api/schema.d.ts` depuis `services/api/openapi.json` |

## Organisation

```
src/
├── api/          # client typé (openapi-fetch), requêtes TanStack Query, erreurs RFC 9457
├── auth/         # session, connexion, utilisateur courant
├── components/   # mise en page, badges, pagination…
├── pages/        # un fichier par écran ; internship/ pour la page d'un stage
├── lib/          # dates, semaines ISO, libellés
└── test/         # fausse API (MSW), données et rendu de test
```

Après une modification de l'API : `make openapi` (à la racine) met à jour le
contrat et les types, puis TypeScript signale tout ce qu'il faut adapter.
