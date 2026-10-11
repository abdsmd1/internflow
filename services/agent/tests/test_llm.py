from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langchain_ollama import ChatOllama

from internflow_agent.config import AgentSettings
from internflow_agent.llm import build_chat_model, warm_up
from internflow_agent.main import create_app
from tests.fakes import ScriptedModel, say


def test_ollama_is_the_default_provider() -> None:
    model = build_chat_model(AgentSettings(_env_file=None, ollama_url="http://ollama:11434"))
    assert isinstance(model, ChatOllama)
    assert model.model == "qwen2.5:3b"
    assert model.temperature == 0
    assert (model.keep_alive, model.num_ctx, model.num_predict) == ("30m", 4096, 512)


def test_paid_providers_need_their_optional_dependency() -> None:
    with pytest.raises(ModuleNotFoundError):
        build_chat_model(AgentSettings(_env_file=None, llm_provider="anthropic"))


def test_warm_up_loads_the_model_and_survives_failures() -> None:
    ready = ScriptedModel(script=[say("prêt")])
    warm_up(ready)
    assert ready.script == []  # le modèle a bien été sollicité

    down = ScriptedModel(script=[])
    down.script.append(ConnectionError("Ollama arrêté"))
    warm_up(down)  # ne lève rien : l'erreur est seulement journalisée


def test_the_service_starts_even_when_ollama_is_down() -> None:
    settings = AgentSettings(_env_file=None, ollama_url="http://127.0.0.1:9", llm_timeout_seconds=2)
    with TestClient(create_app(settings)) as client:  # préchargement en arrière-plan
        assert client.get("/health/live").status_code == 200
