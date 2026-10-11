"""Le contrat OpenAPI commité doit toujours correspondre au code de l'API.

Le frontend génère ses types TypeScript à partir de ce fichier : s'il est périmé,
le frontend compilerait contre une API qui n'existe plus.
"""

from __future__ import annotations

import json
from pathlib import Path

from internflow_api import cli
from internflow_api.openapi_export import render_openapi

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.json"


def test_committed_contract_is_up_to_date() -> None:
    assert CONTRACT.read_text(encoding="utf-8") == render_openapi(), (
        "services/api/openapi.json est périmé : lancez `make openapi`."
    )


def test_contract_exposes_the_bearer_scheme() -> None:
    schema = json.loads(render_openapi())
    assert "OAuth2PasswordBearer" in schema["components"]["securitySchemes"]
    assert "/api/v1/auth/token" in schema["paths"]


def test_cli_writes_the_contract(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    assert cli.main(["export-openapi", "--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == render_openapi()
