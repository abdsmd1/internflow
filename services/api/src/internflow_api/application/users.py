"""Cas d'usage liés aux comptes utilisateurs et à l'authentification."""

from __future__ import annotations

from dataclasses import dataclass

from internflow_api.domain.authorization import require_role
from internflow_api.domain.exceptions import (
    AccountAlreadyLinkedError,
    EmailAlreadyUsedError,
    InternNotFoundError,
    InvalidCredentialsError,
    InvalidValueError,
    SupervisorNotFoundError,
    WeakPasswordError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.security import AccessToken, PasswordHasher, TokenService
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.user import Principal, Role, User
from internflow_api.domain.value_objects import Email

# Recommandations OWASP / NIST SP 800-63B : la longueur prime sur la complexité.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
# En dessous, l'identifiant (ex. « s » de s@ex.com) bannirait presque tout mot de passe.
_MIN_IDENTIFIER_LENGTH_TO_CHECK = 4


def validate_password(password: str, email: Email) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Le mot de passe doit contenir entre {MIN_PASSWORD_LENGTH} "
            f"et {MAX_PASSWORD_LENGTH} caractères."
        )
    identifier = email.value.split("@")[0]
    if len(identifier) >= _MIN_IDENTIFIER_LENGTH_TO_CHECK and identifier in password.lower():
        raise WeakPasswordError("Le mot de passe ne doit pas contenir l'identifiant de l'e-mail.")


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str
    role: Role
    intern_id: InternId | None = None
    supervisor_id: SupervisorId | None = None


class RegisterUser:
    """Crée un compte, sans contrôle d'autorisation.

    Réservé aux points d'entrée de confiance : la ligne de commande d'administration
    (création du premier compte RH) et `CreateUserAccount` ci-dessous.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock, hasher: PasswordHasher) -> None:
        self._uow = uow
        self._clock = clock
        self._hasher = hasher

    def execute(self, command: RegisterUserCommand) -> User:
        email = Email(command.email)
        validate_password(command.password, email)
        with self._uow as uow:
            if uow.users.get_by_email(email) is not None:
                raise EmailAlreadyUsedError(email.value)
            if command.intern_id is not None:
                if uow.interns.get(command.intern_id) is None:
                    raise InternNotFoundError(command.intern_id)
                if uow.users.exists_for_profile(intern_id=command.intern_id):
                    raise AccountAlreadyLinkedError(command.intern_id)
            if command.supervisor_id is not None:
                if uow.supervisors.get(command.supervisor_id) is None:
                    raise SupervisorNotFoundError(command.supervisor_id)
                if uow.users.exists_for_profile(supervisor_id=command.supervisor_id):
                    raise AccountAlreadyLinkedError(command.supervisor_id)

            user = User(
                email=email,
                password_hash=self._hasher.hash(command.password),
                role=command.role,
                intern_id=command.intern_id,
                supervisor_id=command.supervisor_id,
                created_at=self._clock.now(),
            )
            uow.users.add(user)
            uow.commit()
        return user


class CreateUserAccount:
    """Un RH crée le compte d'un collaborateur, d'un encadrant ou d'un stagiaire."""

    def __init__(self, register: RegisterUser) -> None:
        self._register = register

    def execute(self, actor: Principal, command: RegisterUserCommand) -> User:
        require_role(actor, Role.HR)
        return self._register.execute(command)


class Authenticate:
    """Échange un e-mail et un mot de passe contre un jeton d'accès."""

    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, tokens: TokenService) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens

    def execute(self, email: str, password: str) -> AccessToken:
        try:
            normalized = Email(email)
        except InvalidValueError:
            normalized = None
        with self._uow as uow:
            user = uow.users.get_by_email(normalized) if normalized else None
        # Toujours vérifier un mot de passe (factice si besoin) : durée constante.
        valid = self._hasher.verify(user.password_hash if user else None, password)
        if user is None or not valid or not user.is_active:
            raise InvalidCredentialsError
        return self._tokens.issue(user.to_principal())
