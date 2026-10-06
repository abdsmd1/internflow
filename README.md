# InternFlow

Plateforme de gestion automatisée des stagiaires : recrutement, suivi, évaluation,
analytique (PySpark) et assistant IA.

> **Phase 3 — en cours :** pipeline PySpark bronze → silver → gold (indicateurs pseudonymisés). Prochaine étape : orchestration et agent IA.

## Démarrage rapide

Prérequis : [uv](https://docs.astral.sh/uv/), Docker, Make.

```bash
cp .env.example .env      # puis changer POSTGRES_PASSWORD et INTERNFLOW_JWT_SECRET
make install              # dépendances + hooks Git
make check                # lint + typage + tests
make up                   # PostgreSQL + migrations + API
make create-hr email=rh@exemple.ma   # premier compte RH (mot de passe demandé)
```

Indicateurs avec PySpark (après avoir défini `INTERNFLOW_DATA_PSEUDONYMIZATION_SALT` dans `.env`) :

```bash
docker compose run --rm data seed        # données fictives réalistes
docker compose run --rm data pipeline    # bronze → silver → gold dans data/lake/
```

Détails : [`data/README.md`](data/README.md).

Documentation interactive : http://localhost:8000/docs — bouton **Authorize** pour se connecter
(le champ *username* contient l'e-mail).

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=rh@exemple.ma" -d "password=votre-mot-de-passe" | jq -r .access_token)

curl -X POST http://localhost:8000/api/v1/interns \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"first_name":"Sara","last_name":"El Amrani","email":"sara@example.com","school":"ENSA Oujda","study_level":"ingenieur"}'
```

## Structure

```
internflow/
├── services/
│   └── api/                    # API FastAPI (architecture hexagonale)
│       ├── src/internflow_api/
│       │   ├── domain/         # règles métier pures — aucun framework
│       │   ├── application/    # cas d'usage
│       │   ├── infrastructure/ # PostgreSQL, horloge, logs
│       │   ├── presentation/   # routes HTTP, DTO, erreurs
│       │   └── main.py         # composition root
│       ├── migrations/         # Alembic
│       └── tests/              # unit / e2e / integration
├── data/                       # seed + pipeline PySpark (bronze / silver / gold)
│   ├── src/internflow_data/
│   │   ├── transformations/    # fonctions pures, testées sans base
│   │   ├── jobs/               # extract → refine → aggregate
│   │   └── seed/               # historique fictif via les entités du domaine
│   └── tests/
├── docs/
│   ├── adr/                    # décisions d'architecture
│   └── architecture/           # diagrammes C4
├── .github/workflows/ci.yml    # lint, typage, tests, sécurité, image Docker
├── docker-compose.yml
└── Makefile                    # make help
```

## Qualité : ce qui est vérifié automatiquement

| Contrôle | Outil | Quand |
|----------|-------|-------|
| Style, bugs, sécurité, imports | Ruff | pre-commit + CI |
| Règle de dépendance hexagonale | Ruff `TID251` | pre-commit + CI |
| Typage strict | mypy `--strict` | pre-commit + CI |
| Tests + couverture ≥ 85 % | pytest | CI |
| Migrations réversibles | test « escalier » Alembic | CI |
| Migrations à jour avec le modèle | `alembic check` | CI |
| Qualité des données (unicité, bornes, cohérence) | contrôles PySpark bloquants | à chaque exécution du pipeline |
| Secrets dans le code | gitleaks | pre-commit + CI |
| Vulnérabilités | pip-audit, Trivy | CI |
| Messages de commit | Commitizen (Conventional Commits) | commit-msg |

## Tests

```bash
make test-unit          # ~1 s, sans base de données
make test-integration   # vrai PostgreSQL via Testcontainers (Docker requis)
make test               # tout, avec couverture
make test-data          # pipeline PySpark (Java 17+ requis)
```

Pour lancer les tests d'intégration contre une base existante :
`INTERNFLOW_TEST_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db make test-integration`

## Conventions

- **Branches** : `feat/…`, `fix/…`, `docs/…` — jamais de commit direct sur `main`.
- **Commits** : [Conventional Commits](https://www.conventionalcommits.org/fr/) — `feat(api): ajouter la liste paginée`.
- **Schéma de base** : uniquement via `make migration m="…"`, migration relue et réversible.
- **Décisions** : un ADR dans `docs/adr/` pour tout choix structurant.
- **Données** : uniquement des données fictives ; aucune donnée personnelle réelle dans le dépôt.

## Feuille de route

1. ✅ Socle, module Stagiaires
2. ✅ Phase 2
   - ✅ Encadrants et stages (machine à états, contraintes d'intégrité) — [ADR 0006](docs/adr/0006-stages-machine-a-etats-et-integrite.md)
   - ✅ Authentification JWT + rôles (RH, encadrant, stagiaire) — [ADR 0007](docs/adr/0007-authentification-jwt-et-roles.md)
   - ✅ Tâches et rapports hebdomadaires — [ADR 0008](docs/adr/0008-taches-et-rapports-hebdomadaires.md)
3. ⏳ Phase 3 — données
   - ✅ Pipeline PySpark bronze / silver / gold, données fictives réalistes — [ADR 0009](docs/adr/0009-pipeline-pyspark-medaillon.md)
   - ⏳ Orchestration Airflow, stockage MinIO
4. ⏳ Modèle de matching candidat ↔ offre (MLlib, MLflow)
5. ⏳ Agent IA (LangGraph, RAG sur pgvector, validation humaine)
6. ⏳ Frontend React, observabilité
