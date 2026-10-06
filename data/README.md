# internflow-data

Traitements de données d'InternFlow : génération de données fictives (`seed`) et
pipeline PySpark **bronze → silver → gold** (`pipeline`). Les choix sont
expliqués dans l'[ADR 0009](../docs/adr/0009-pipeline-pyspark-medaillon.md).

## Utilisation avec Docker (recommandé, Java inutile sur le poste)

```bash
# Une seule fois : définir INTERNFLOW_DATA_PSEUDONYMIZATION_SALT dans .env
docker compose run --rm data seed --interns 200       # données fictives
docker compose run --rm data pipeline                 # date du jour
docker compose run --rm data pipeline --date 2026-10-06 --step aggregate
docker compose run --rm data show internship_kpis --limit 5   # aperçu lisible
```

Les résultats apparaissent dans `data/lake/` (ignoré par Git).

## Organisation

```
src/internflow_data/
├── config.py               # paramètres (préfixe INTERNFLOW_DATA_)
├── spark.py                # session Spark (UTC, écrasement dynamique)
├── schemas.py              # requêtes d'extraction minimisées + contrats StructType
├── quality.py              # contrôles qualité bloquants
├── transformations/
│   ├── silver.py           # nettoyage, pseudonymisation, colonnes dérivées
│   └── gold.py             # indicateurs
├── jobs/                   # extract → refine → aggregate (lecture / écriture)
├── seed/generator.py       # historique réaliste via les entités du domaine
└── __main__.py             # ligne de commande
```

Les **transformations** sont des fonctions pures (`DataFrame → DataFrame`) ; les
**jobs** se chargent des lectures et écritures. C'est ce découpage qui rend les
indicateurs testables sans base de données.

## Indicateurs (gold)

| Jeu | Grain | Exemples de colonnes |
|-----|-------|----------------------|
| `internship_kpis` | un stage en cours ou terminé | `on_time_rate`, `overdue_open_tasks`, `report_regularity`, `avg_review_lag_days` |
| `supervisor_workload` | un encadrant | `active_internships`, `utilization`, `pending_reviews` |
| `weekly_activity` | une semaine ISO | `reports_submitted`, `tasks_completed` |

Chaque jeu est partitionné par `as_of` : un instantané par date de calcul.

## Tests

Nécessitent Java 17 ou plus récent.

```bash
cd data
uv run pytest -m "not integration" --no-cov   # transformations et générateur
INTERNFLOW_TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/db \
INTERNFLOW_DATA_JDBC_DRIVER_JAR=/chemin/postgresql.jar \
uv run pytest                          # + bout en bout sur PostgreSQL
```
