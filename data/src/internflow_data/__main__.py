"""Ligne de commande des traitements de données.

python -m internflow_data seed --interns 200          # données fictives dans PostgreSQL
python -m internflow_data pipeline                    # bronze → silver → gold (aujourd'hui)
python -m internflow_data pipeline --step aggregate --date 2026-10-06
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from pyspark.sql import functions as F
from sqlalchemy.orm import sessionmaker

from internflow_api.config import DatabaseSettings
from internflow_api.domain.exceptions import DomainError
from internflow_api.infrastructure.persistence.sqlalchemy_uow import (
    SqlAlchemyUnitOfWork,
    build_engine,
)
from internflow_data.config import DataSettings
from internflow_data.jobs.aggregate import aggregate, gold_path
from internflow_data.jobs.extract import extract
from internflow_data.jobs.refine import refine
from internflow_data.quality import DataQualityError
from internflow_data.seed.generator import HistoryGenerator, SeedConfig, persist
from internflow_data.spark import build_spark_session

STEPS = ("extract", "refine", "aggregate")
INDICATORS = ("internship_kpis", "supervisor_workload", "weekly_activity")


def _today() -> date:
    return datetime.now(UTC).date()


def run_seed(args: argparse.Namespace) -> int:
    config = SeedConfig(supervisors=args.supervisors, interns=args.interns, seed=args.seed)
    data = HistoryGenerator(config, today=args.date).generate()
    engine = build_engine(DatabaseSettings().database_url.unicode_string(), pool_size=1)
    try:
        persist(data, SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False)))
    except DomainError as error:
        print(
            f"Erreur : {error}\nCes données ont sans doute déjà été générées : "
            "relancez avec une autre valeur de --seed.",
            file=sys.stderr,
        )
        return 1
    finally:
        engine.dispose()
    print(
        f"Données générées : {len(data.supervisors)} encadrants, {len(data.interns)} stagiaires, "
        f"{len(data.internships)} stages, {len(data.tasks)} tâches, {len(data.reports)} rapports."
    )
    return 0


def run_pipeline(args: argparse.Namespace) -> int:
    settings = DataSettings()  # type: ignore[call-arg]  # valeurs lues dans l'environnement
    steps = STEPS if args.step == "all" else (args.step,)
    spark = build_spark_session(
        "internflow-pipeline", master=settings.spark_master, jars=[settings.jdbc_driver_jar]
    )
    try:
        for step in steps:
            started = time.perf_counter()
            match step:
                case "extract":
                    counts = extract(spark, settings, args.date)
                case "refine":
                    counts = refine(spark, settings, args.date)
                case _:
                    counts = aggregate(spark, settings, args.date)
            details = ", ".join(f"{name}={rows}" for name, rows in counts.items())
            print(f"[{step}] {details} ({time.perf_counter() - started:.1f} s)")
    except DataQualityError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 2
    finally:
        spark.stop()
    return 0


def run_show(args: argparse.Namespace) -> int:
    settings = DataSettings()  # type: ignore[call-arg]
    spark = build_spark_session("internflow-show", master=settings.spark_master, jars=None)
    try:
        path = Path(gold_path(settings, args.indicator)) / f"as_of={args.date.isoformat()}"
        if not path.is_dir():
            print(f"Aucun instantané {args.indicator} au {args.date} : lancez d'abord `pipeline`.")
            return 1
        df = spark.read.parquet(str(path))
        print(f"{args.indicator} au {args.date} : {df.count()} lignes")
        # Clés pseudonymisées tronquées pour la lisibilité.
        keys = [c for c in df.columns if c.endswith("_key")]
        df.select(*[F.substring(c, 1, 8).alias(c) if c in keys else c for c in df.columns]).show(
            args.limit, truncate=False
        )
    finally:
        spark.stop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="internflow-data", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    seed = commands.add_parser("seed", help="Générer des données fictives réalistes")
    seed.add_argument("--supervisors", type=int, default=20)
    seed.add_argument("--interns", type=int, default=200)
    seed.add_argument("--seed", type=int, default=42, help="graine aléatoire (reproductible)")
    seed.add_argument("--date", type=date.fromisoformat, default=_today(), help="« aujourd'hui »")

    pipeline = commands.add_parser("pipeline", help="Exécuter le pipeline PySpark")
    pipeline.add_argument("--step", choices=("all", *STEPS), default="all")
    pipeline.add_argument("--date", type=date.fromisoformat, default=_today())

    show = commands.add_parser("show", help="Afficher un indicateur gold")
    show.add_argument("indicator", choices=INDICATORS)
    show.add_argument("--date", type=date.fromisoformat, default=_today())
    show.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    match args.command:
        case "seed":
            return run_seed(args)
        case "pipeline":
            return run_pipeline(args)
        case _:
            return run_show(args)


if __name__ == "__main__":
    raise SystemExit(main())
