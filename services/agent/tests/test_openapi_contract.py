from __future__ import annotations

from pathlib import Path

from internflow_agent.openapi_export import main, render_openapi

CONTRACT = Path(__file__).resolve().parents[1] / "openapi.json"


def test_committed_contract_is_up_to_date() -> None:
    assert CONTRACT.read_text(encoding="utf-8") == render_openapi(), (
        "services/agent/openapi.json est périmé : lancez `make openapi`."
    )


def test_cli(tmp_path: Path) -> None:
    output = tmp_path / "contrat.json"
    assert main([str(output)]) == 0
    assert output.read_text(encoding="utf-8") == render_openapi()
    assert main([]) == 2
