from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from langchain_core.messages import AIMessage

from internflow_agent.config import AgentSettings
from internflow_agent.main import create_app
from tests.fakes import FakeApi, ScriptedModel

TODAY = date(2026, 10, 14)


class Harness:
    """Monte l'application avec un modèle scénarisé et une fausse API partagée."""

    def __init__(self) -> None:
        self.model = ScriptedModel(script=[])
        self.apis: dict[str, FakeApi] = {}
        self.app = create_app(
            AgentSettings(_env_file=None, max_steps=3),
            model=self.model,
            api_factory=self.api_for,
            today=lambda: TODAY,
        )
        self.client = TestClient(self.app)

    def api_for(self, token: str) -> FakeApi:
        # Une même fausse API par jeton : on peut vérifier ce qui a été créé.
        return self.apis.setdefault(token, FakeApi(token))

    def script(self, *steps: AIMessage | Exception) -> None:
        self.model.script.extend(steps)

    def chat(
        self, message: str, *, token: str = "jeton-encadrant", thread_id: str | None = None
    ) -> Response:
        body = {"message": message, **({"thread_id": thread_id} if thread_id else {})}
        return self.client.post(
            "/api/v1/agent/chat", json=body, headers={"Authorization": f"Bearer {token}"}
        )

    def decide(self, thread_id: str, approved: bool, *, token: str = "jeton-encadrant") -> Response:
        return self.client.post(
            f"/api/v1/agent/threads/{thread_id}/decision",
            json={"approved": approved},
            headers={"Authorization": f"Bearer {token}"},
        )


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.fixture
def make_api() -> Callable[..., FakeApi]:
    return FakeApi
