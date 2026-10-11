"""Le jeu d'évaluation s'exécute de bout en bout (ici avec un modèle scénarisé)."""

from __future__ import annotations

import pytest

from internflow_agent import evals
from tests.fakes import ScriptedModel, call, say


def scripted(_settings: object) -> ScriptedModel:
    # Bonne réponse à la 1re question ; « Je ne sais pas » ensuite, ce qui réussit
    # aussi les deux cas où il ne faut surtout rien faire : score de 3 sur 8.
    script = [call("taches_en_retard"), say("« Modéliser la base de données » est en retard.")]
    return ScriptedModel(script=script + [say("Je ne sais pas.")] * (len(evals.CASES) - 1))


def test_evaluation_reports_each_case_and_the_score(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(evals, "build_chat_model", scripted)
    assert evals.main(["--min-score", "0.1"]) == 0
    output = capsys.readouterr().out
    assert "✅ tâches en retard" in output
    assert "❌ rapports à relire" in output
    assert "✅ consigne cachée dans un rapport" in output
    assert f"Score : 3/{len(evals.CASES)}" in output


def test_evaluation_fails_below_the_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals, "build_chat_model", scripted)
    assert evals.main(["--min-score", "0.8"]) == 1
