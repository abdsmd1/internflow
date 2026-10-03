# internflow-api

Service API d'InternFlow — voir le [README racine](../../README.md) et
l'[ADR 0002](../../docs/adr/0002-architecture-hexagonale.md) pour l'architecture.

## Ajouter une fonctionnalité : l'ordre à suivre

1. **Domaine** — entité / value object + règles, avec leurs tests unitaires.
2. **Port** — si une nouvelle dépendance externe est nécessaire (`domain/ports/`).
3. **Cas d'usage** — dans `application/`, testé avec l'adaptateur en mémoire.
4. **Adaptateur** — implémentation SQLAlchemy + migration Alembic + test d'intégration.
5. **Présentation** — DTO Pydantic, route, test e2e. Une nouvelle exception métier
   n'a rien à déclarer : sa catégorie fixe le statut HTTP, son `code` le type d'erreur.

## Règles métier des stages

| Règle | Erreur (`type`) | HTTP |
|---|---|---|
| Fin postérieure au début, durée ≤ 183 jours, fin non passée | `invalid-value` | 422 |
| Pas deux stages actifs qui se chevauchent pour un stagiaire | `internship-overlap` | 409 |
| L'encadrant ne dépasse pas sa capacité sur la période | `supervisor-capacity-exceeded` | 409 |
| Démarrage seulement à partir de la date de début | `internship-not-startable-yet` | 409 |
| Transitions : planned → ongoing → completed ; planned/ongoing → cancelled | `invalid-status-transition` | 409 |

## Endpoints

Toutes les routes `/api/v1/*` exigent `Authorization: Bearer <jeton>`, sauf la connexion.
Les sondes `/health/*` restent publiques. Droits par rôle : voir
[ADR 0007](../../docs/adr/0007-authentification-jwt-et-roles.md).

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `POST` | `/api/v1/auth/token` | Se connecter (formulaire OAuth2 : `username` = e-mail) → jeton JWT |
| `GET` | `/api/v1/auth/me` | Identité et rôle de l'appelant |
| `POST` | `/api/v1/users` | Créer un compte (RH) — lié à un profil stagiaire ou encadrant selon le rôle |
| `POST` | `/api/v1/interns` | Inscrire un stagiaire (201 + `Location`, 409 si e-mail déjà utilisé) |
| `GET` | `/api/v1/interns/{id}` | Consulter un stagiaire (404 si absent) |
| `GET` | `/api/v1/interns?offset=&limit=` | Lister, du plus récent au plus ancien (limit ≤ 100) |
| `POST` | `/api/v1/supervisors` | Enregistrer un encadrant (capacité `max_interns`, 5 par défaut) |
| `GET` | `/api/v1/supervisors/{id}` | Consulter un encadrant |
| `GET` | `/api/v1/supervisors?offset=&limit=` | Lister les encadrants |
| `POST` | `/api/v1/internships` | Planifier un stage (404 si stagiaire/encadrant inconnu, 409 si chevauchement ou capacité atteinte) |
| `GET` | `/api/v1/internships/{id}` | Consulter un stage |
| `GET` | `/api/v1/internships?intern_id=&supervisor_id=&status=` | Lister les stages (filtres combinables) |
| `POST` | `/api/v1/internships/{id}/start` | Démarrer (à partir de la date de début) |
| `POST` | `/api/v1/internships/{id}/complete` | Terminer un stage en cours |
| `POST` | `/api/v1/internships/{id}/cancel` | Annuler un stage prévu ou en cours |
| `GET` | `/health/live` | Sonde de vivacité |
| `GET` | `/health/ready` | Sonde de disponibilité (vérifie PostgreSQL) |

## Lancer sans Docker

```bash
make migrate
uv run python -m internflow_api.cli create-hr-user --email rh@exemple.ma
uv run uvicorn internflow_api.main:create_app --factory --reload
```
