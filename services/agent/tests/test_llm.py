from __future__ import annotations

import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr, ValidationError

from internflow_agent.config import AgentSettings
from internflow_agent.llm import build_chat_model, warm_up
from internflow_agent.main import create_app
from tests.conftest import Harness
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


def test_openai_compatible_provider_defaults_to_groq() -> None:
    settings = AgentSettings(
        _env_file=None,
        llm_provider="openai",
        llm_model="openai/gpt-oss-120b",
        llm_api_key=SecretStr("cle-de-test"),
    )
    model = build_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "openai/gpt-oss-120b"
    assert model.openai_api_base == "https://api.groq.com/openai/v1"
    assert model.temperature == 0


def test_cloud_provider_requires_a_key() -> None:
    with pytest.raises(ValidationError, match="INTERNFLOW_AGENT_LLM_API_KEY"):
        AgentSettings(_env_file=None, llm_provider="openai")
    with pytest.raises(ValidationError, match=r"console\.groq\.com"):  # variable vide
        AgentSettings(_env_file=None, llm_provider="openai", llm_api_key=SecretStr(""))


def test_cloud_errors_are_reported_as_model_unavailable(harness: Harness) -> None:
    request = httpx2.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    harness.script(
        openai.RateLimitError("quota", response=httpx2.Response(429, request=request), body=None)
    )
    response = harness.chat("Bonjour")
    assert response.status_code == 503
    assert "quota" in response.json()["detail"]
