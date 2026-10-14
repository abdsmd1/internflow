"""Création du modèle de langage selon la configuration."""

from __future__ import annotations

import importlib

import httpx
import openai
import structlog
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from ollama import ResponseError

from internflow_agent.config import AgentSettings

logger = structlog.get_logger(__name__)

# Erreurs signifiant « le modèle n'est pas joignable ou pas prêt » (Ollama arrêté,
# modèle pas téléchargé, délai dépassé, quota ou clé refusés par l'API cloud) :
# l'assistant répond alors 503.
MODEL_UNAVAILABLE_ERRORS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    httpx.TransportError,
    ResponseError,
    openai.APIError,
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

    if settings.llm_provider == "openai":
        if settings.llm_api_key is None:  # déjà refusé par AgentSettings ; garde pour mypy
            raise ValueError("Clé d'API manquante.")
        return ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.openai_base_url,
            api_key=settings.llm_api_key,
            temperature=0,
            max_completion_tokens=settings.llm_max_answer_tokens,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,  # absorbe un dépassement ponctuel de quota (erreur 429)
        )

    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_url,
        temperature=0,  # réponses reproductibles : l'assistant ne doit pas « improviser »
        keep_alive=settings.llm_keep_alive,
        num_ctx=settings.llm_context_tokens,
        num_predict=settings.llm_max_answer_tokens,
        client_kwargs={"timeout": settings.llm_timeout_seconds},
    )


def warm_up(model: BaseChatModel) -> None:
    """Fait charger le modèle par Ollama ; une erreur ici n'empêche pas le démarrage."""
    try:
        model.invoke("Réponds simplement : prêt.")
        logger.info("model_ready")
    except MODEL_UNAVAILABLE_ERRORS as error:
        logger.warning("model_warmup_failed", error=type(error).__name__, detail=describe(error))


def describe(error: BaseException) -> str:
    """Message d'erreur court pour les journaux (le fournisseur n'y met jamais la clé)."""
    return str(error).replace("\n", " ")[:200]
