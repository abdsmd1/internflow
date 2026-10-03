"""La commande d'administration crée un vrai compte RH dans PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, text

from internflow_api import cli
from tests.factories import TEST_PASSWORD

pytestmark = pytest.mark.integration


@pytest.fixture
def database_env(monkeypatch: pytest.MonkeyPatch, engine: Engine, database_url: str) -> None:
    monkeypatch.setenv("INTERNFLOW_DATABASE_URL", database_url)
    monkeypatch.setenv(cli.PASSWORD_ENV_VAR, TEST_PASSWORD)


@pytest.mark.usefixtures("database_env")
def test_create_hr_user(engine: Engine, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["create-hr-user", "--email", "admin@example.com"]) == 0
    assert "Compte RH créé" in capsys.readouterr().out
    with engine.connect() as connection:
        role = connection.execute(
            text("SELECT role FROM users WHERE email = 'admin@example.com'")
        ).scalar_one()
    assert role == "hr"


@pytest.mark.usefixtures("database_env")
def test_errors_are_reported_without_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["create-hr-user", "--email", "admin@example.com"]) == 0
    assert cli.main(["create-hr-user", "--email", "admin@example.com"]) == 1
    assert "déjà utilisée" in capsys.readouterr().err
