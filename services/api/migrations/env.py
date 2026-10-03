"""Environnement Alembic : URL lue depuis la configuration de l'application."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from internflow_api.config import DatabaseSettings
from internflow_api.infrastructure.persistence.orm import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Permet aux tests de surcharger l'URL ; sinon on lit INTERNFLOW_DATABASE_URL.
# Les migrations n'ont besoin que de la base : pas du secret JWT (moindre privilège).
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", DatabaseSettings().database_url.unicode_string())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Génère le SQL sans connexion (utile pour une revue par un DBA)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
