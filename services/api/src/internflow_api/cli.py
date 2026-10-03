"""Commandes d'administration (point d'entrée de confiance, exécuté sur le serveur).

Créer le premier compte RH :
    python -m internflow_api.cli create-hr-user --email rh@exemple.ma

Le mot de passe est demandé de façon masquée, ou lu dans la variable
INTERNFLOW_BOOTSTRAP_PASSWORD (utile en automatisation). Il n'existe aucun
compte ni mot de passe par défaut.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from collections.abc import Sequence

from sqlalchemy.orm import sessionmaker

from internflow_api.application.users import RegisterUser, RegisterUserCommand
from internflow_api.config import DatabaseSettings
from internflow_api.domain.exceptions import DomainError
from internflow_api.domain.user import Role
from internflow_api.infrastructure.clock import SystemClock
from internflow_api.infrastructure.persistence.sqlalchemy_uow import (
    SqlAlchemyUnitOfWork,
    build_engine,
)
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher

PASSWORD_ENV_VAR = "INTERNFLOW_BOOTSTRAP_PASSWORD"  # noqa: S105 (nom de variable, pas un secret)


def _read_password() -> str:
    if from_env := os.environ.get(PASSWORD_ENV_VAR):
        return from_env
    password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
    if password != getpass.getpass("Confirmation : "):
        raise SystemExit("Les deux mots de passe ne correspondent pas.")
    return password


def create_hr_user(email: str, password: str) -> str:
    engine = build_engine(DatabaseSettings().database_url.unicode_string(), pool_size=1)
    try:
        uow = SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))
        user = RegisterUser(uow, SystemClock(), Argon2PasswordHasher()).execute(
            RegisterUserCommand(email=email, password=password, role=Role.HR)
        )
    finally:
        engine.dispose()  # ferme les connexions : la commande se termine proprement
    return str(user.id)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="internflow-admin", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-hr-user", help="Créer un compte RH")
    create.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    if args.command == "create-hr-user":
        try:
            user_id = create_hr_user(args.email, _read_password())
        except DomainError as error:
            print(f"Erreur : {error}", file=sys.stderr)
            return 1
        print(f"Compte RH créé : {args.email} (id {user_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
