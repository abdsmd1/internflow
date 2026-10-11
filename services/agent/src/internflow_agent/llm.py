"""Création du modèle de langage selon la configuration."""

from __future__ import annotations

import importlib

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from ollama import ResponseError

from internflow_agent.config import AgentSettings

# Erreurs signifiant « le modèle n'est pas joignable ou pas prêt » (Ollama arrêté,
# modèle pas encore téléchargé, délai dépassé) : l'API répond alors 503.
MODEL_UNAVAILABLE_ERRORS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    httpx.TransportError,
    ResponseError,
)


def build_chat_model(settings: AgentSettings) -> BaseChatModel:
    if settings.llm_provider == "anthropic":
        # Chargé dynamiquement : la dépendance n'est installée que si on choisit ce
        # fournisseur (`uv sync --extra anthropic`). La clé est lue dans ANTHROPIC_API_KEY.
        chat_anthropic = importlib.import_module("langchain_anthropic").ChatAnthropic
        model: BaseChatModel = chat_anthropic(
            model_name=settings.llm_model, temperature=0, timeout=settings.llm_timeout_seconds
        )
        return model

    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_url,
        temperature=0,  # réponses reproductibles : l'assistant ne doit pas « improviser »
        client_kwargs={"timeout": settings.llm_timeout_seconds},
    )
