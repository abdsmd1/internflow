"""Fabriques de données de test réutilisables (importables, contrairement à conftest)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from internflow_api.config import Environment, Settings
from internflow_api.domain.user import Principal, Role, UserId
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher

FIXED_NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

# Identité « RH » pour appeler directement les cas d'usage dans les tests unitaires.
HR = Principal(UserId(uuid4()), Role.HR)

# Généré à chaque exécution : aucun secret, même factice, n'est écrit dans le dépôt.
TEST_JWT_SECRET = secrets.token_urlsafe(32)
HR_EMAIL = "rh@example.com"
TEST_PASSWORD = "une-phrase-de-passe-solide"


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.TEST,
        "log_level": "WARNING",
        "jwt_secret": TEST_JWT_SECRET,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def fast_hasher() -> Argon2PasswordHasher:
    """Argon2 avec des paramètres allégés : même algorithme, tests rapides."""
    return Argon2PasswordHasher(time_cost=1, memory_cost_kib=1024)


class FakeClock:
    """Horloge contrôlable : chaque appel avance d'une seconde (ordre déterministe)."""

    def __init__(self, start: datetime = FIXED_NOW) -> None:
        self._current = start

    def now(self) -> datetime:
        value = self._current
        self._current += timedelta(seconds=1)
        return value


def intern_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Sara",
        "last_name": "El Amrani",
        "email": "sara.elamrani@example.com",
        "school": "ENSA Oujda",
        "study_level": "ingenieur",
    }
    payload.update(overrides)
    return payload


def supervisor_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Karim",
        "last_name": "Benali",
        "email": "karim.benali@example.com",
        "department": "Data & IA",
    }
    payload.update(overrides)
    return payload


def internship_payload(
    intern_id: str, supervisor_id: str, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "intern_id": intern_id,
        "supervisor_id": supervisor_id,
        "subject": "Agent IA de suivi des stagiaires",
        "start_date": "2026-10-05",
        "end_date": "2027-02-05",
    }
    payload.update(overrides)
    return payload
