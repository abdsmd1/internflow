"""Export du contrat OpenAPI de l'assistant, source des types TypeScript du frontend.

python -m internflow_agent.openapi_export openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from internflow_agent.config import AgentSettings
from internflow_agent.main import create_app


def build_openapi_schema() -> dict[str, Any]:
    # Le modèle Ollama n'est pas contacté : le construire suffit pour décrire l'API.
    return create_app(AgentSettings(_env_file=None)).openapi()


def render_openapi() -> str:
    return json.dumps(build_openapi_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage : python -m internflow_agent.openapi_export <fichier>", file=sys.stderr)
        return 2
    Path(args[0]).write_text(render_openapi(), encoding="utf-8")
    print(f"Contrat OpenAPI écrit dans {args[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
