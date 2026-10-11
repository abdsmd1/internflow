"""Export du contrat OpenAPI, source de vérité des types du frontend.

Le fichier `services/api/openapi.json` est commité : un test vérifie qu'il
correspond toujours au code, et le frontend en génère ses types TypeScript.
"""

from __future__ import annotations

import json
import secrets
from typing import Any

from pydantic import SecretStr

from internflow_api.config import Environment, Settings
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from internflow_api.main import create_app


def build_openapi_schema() -> dict[str, Any]:
    # Configuration jetable : le schéma ne dépend ni de la base ni du secret JWT.
    settings = Settings(
        _env_file=None,  # ignore le .env local : export reproductible
        environment=Environment.LOCAL,
        jwt_secret=SecretStr(secrets.token_urlsafe(48)),
    )
    uow = InMemoryUnitOfWork()
    app = create_app(settings, uow_factory=lambda: uow, readiness_check=lambda: True)
    return app.openapi()


def render_openapi() -> str:
    """JSON stable (clés triées, indentation fixe) pour des diffs lisibles."""
    return json.dumps(build_openapi_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
