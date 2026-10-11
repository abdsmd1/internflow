from __future__ import annotations

import pytest
from langchain_ollama import ChatOllama

from internflow_agent.config import AgentSettings
from internflow_agent.llm import build_chat_model


def test_ollama_is_the_default_provider() -> None:
    model = build_chat_model(AgentSettings(_env_file=None, ollama_url="http://ollama:11434"))
    assert isinstance(model, ChatOllama)
    assert model.model == "qwen2.5:7b"
    assert model.temperature == 0


def test_paid_providers_need_their_optional_dependency() -> None:
    with pytest.raises(ModuleNotFoundError):
        build_chat_model(AgentSettings(_env_file=None, llm_provider="anthropic"))
