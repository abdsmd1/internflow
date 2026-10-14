"""Configuration de l'agent, lue depuis l'environnement (préfixe INTERNFLOW_AGENT_)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTERNFLOW_AGENT_", env_file=".env", extra="ignore", frozen=True
    )

    # L'agent n'a aucun accès direct à la base : il passe par l'API, comme un client.
    api_url: str = "http://localhost:8000"
    api_timeout_seconds: float = Field(default=10, gt=0, le=60)

    # Fournisseurs :
    # - ollama : modèle libre exécuté en local, sans clé ni coût, mais lent sans carte
    #   graphique (qwen2.5:3b ~2 Go, qwen2.5:7b meilleur mais lourd) ;
    # - openai : toute API compatible OpenAI. Par défaut Groq, gratuit avec une clé et
    #   très rapide (modèles open source hébergés) ;
    # - anthropic : Claude, payant (dépendance optionnelle).
    llm_provider: Literal["ollama", "openai", "anthropic"] = "ollama"
    llm_model: str = "qwen2.5:3b"
    ollama_url: str = "http://localhost:11434"
    openai_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: SecretStr | None = None
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

    @model_validator(mode="after")
    def _key_required_for_cloud(self) -> AgentSettings:
        # Échec au démarrage, avec un message clair, plutôt qu'à la première question.
        missing = self.llm_api_key is None or not self.llm_api_key.get_secret_value()
        if self.llm_provider == "openai" and missing:
            raise ValueError(
                "INTERNFLOW_AGENT_LLM_API_KEY est obligatoire avec le fournisseur « openai » "
                "(clé Groq gratuite : https://console.groq.com/keys)."
            )
        return self


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
