"""Fabriques de données de test réutilisables (importables, contrairement à conftest)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

FIXED_NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


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
