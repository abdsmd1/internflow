"""Configuration de l'agent, lue depuis l'environnement (préfixe INTERNFLOW_AGENT_)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTERNFLOW_AGENT_", env_file=".env", extra="ignore", frozen=True
    )

    # L'agent n'a aucun accès direct à la base : il passe par l'API, comme un client.
    api_url: str = "http://localhost:8000"
    api_timeout_seconds: float = Field(default=10, gt=0, le=60)

    # Ollama par défaut : modèle libre, exécuté en local, sans clé ni coût.
    # qwen2.5:3b (~2 Go) tient dans un portable ; qwen2.5:7b est meilleur mais lourd.
    llm_provider: Literal["ollama", "anthropic"] = "ollama"
    llm_model: str = "qwen2.5:3b"
    ollama_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = Field(default=300, gt=0)
    # Garde le modèle en mémoire entre deux questions (le recharger prend du temps).
    llm_keep_alive: str = "30m"
    # Contexte et réponse bornés : moins de mémoire, réponses plus rapides sur processeur.
    llm_context_tokens: int = Field(default=4096, ge=2048, le=32768)
    llm_max_answer_tokens: int = Field(default=512, ge=64, le=4096)
    # Charge le modèle au démarrage, pour que la première question ne paie pas ce coût.
    llm_warmup: bool = True

    # Garde-fou : nombre maximal d'allers-retours modèle ↔ outils par message.
    max_steps: int = Field(default=8, ge=2, le=20)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
