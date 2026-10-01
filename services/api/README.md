# internflow-api

Service API d'InternFlow — voir le [README racine](../../README.md) et
l'[ADR 0002](../../docs/adr/0002-architecture-hexagonale.md) pour l'architecture.

## Ajouter une fonctionnalité : l'ordre à suivre

1. **Domaine** — entité / value object + règles, avec leurs tests unitaires.
2. **Port** — si une nouvelle dépendance externe est nécessaire (`domain/ports/`).
3. **Cas d'usage** — dans `application/`, testé avec l'adaptateur en mémoire.
4. **Adaptateur** — implémentation SQLAlchemy + migration Alembic + test d'intégration.
5. **Présentation** — DTO Pydantic, route, traduction d'erreur, test e2e.

## Endpoints

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `POST` | `/api/v1/interns` | Inscrire un stagiaire (201 + `Location`, 409 si e-mail déjà utilisé) |
| `GET` | `/api/v1/interns/{id}` | Consulter un stagiaire (404 si absent) |
| `GET` | `/api/v1/interns?offset=&limit=` | Lister, du plus récent au plus ancien (limit ≤ 100) |
| `GET` | `/health/live` | Sonde de vivacité |
| `GET` | `/health/ready` | Sonde de disponibilité (vérifie PostgreSQL) |

## Lancer sans Docker

```bash
make migrate
uv run uvicorn internflow_api.main:create_app --factory --reload
```
