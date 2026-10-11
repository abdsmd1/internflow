"""Parcours complets via HTTP : question, outils, réponse, validation humaine."""

from __future__ import annotations

from langchain_core.messages import SystemMessage, ToolMessage

from internflow_agent.api_client import ApiCallError, ApiUnreachableError, Me
from tests.conftest import Harness
from tests.fakes import call, say


def test_answers_with_the_help_of_a_tool(harness: Harness) -> None:
    harness.script(
        call("taches_en_retard"), say("Une tâche est en retard : « Modéliser la base ».")
    )
    response = harness.chat("Quelles tâches sont en retard ?")

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Une tâche est en retard : « Modéliser la base »."
    assert body["tools_used"] == ["taches_en_retard"]
    assert body["pending_action"] is None
    # Le modèle a bien reçu le résultat de l'outil avant de répondre.
    tool_result = harness.model.received[-1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert "Modéliser la base" in str(tool_result.content)
    assert "Sara El Amrani" in str(tool_result.content)


def test_the_model_knows_the_role_and_the_date(harness: Harness) -> None:
    harness.script(say("Bonjour."))
    harness.chat("Bonjour", token="jeton-rh")
    system = harness.model.received[0][0]
    assert isinstance(system, SystemMessage)
    assert "ressources humaines" in str(system.content)
    assert "2026-10-14" in str(system.content)
    assert "<donnees>" in str(system.content)  # consigne contre l'injection de prompt


def test_a_conversation_keeps_its_history(harness: Harness) -> None:
    harness.script(say("Il y a un stage en cours."), say("Il s'agit de « Agent IA de suivi »."))
    thread_id = harness.chat("Combien de stages ?").json()["thread_id"]
    harness.chat("Lequel ?", thread_id=thread_id)

    contents = [m.content for m in harness.model.received[-1]]
    assert "Combien de stages ?" in contents
    assert "Il y a un stage en cours." in contents
    assert "Lequel ?" in contents


def test_a_conversation_belongs_to_its_author(harness: Harness) -> None:
    harness.script(say("Bonjour."))
    thread_id = harness.chat("Bonjour").json()["thread_id"]

    response = harness.chat("Et moi ?", token="jeton-rh", thread_id=thread_id)
    assert response.status_code == 404
    assert response.json()["type"].endswith("/conversation-not-found")


class TestHumanValidation:
    def propose(self, harness: Harness) -> str:
        harness.script(
            call(
                "proposer_tache",
                stage_id="stage-1",
                titre="Préparer la démo",
                echeance="2026-10-30",
                description="Démo de fin de sprint",
            )
        )
        response = harness.chat("Ajoute une tâche pour préparer la démo le 30 octobre")
        assert response.status_code == 200
        return str(response.json()["thread_id"])

    def test_the_pending_action_is_described(self, harness: Harness) -> None:
        harness.script(
            call(
                "proposer_tache",
                stage_id="stage-1",
                titre="Préparer la démo",
                echeance="2026-10-30",
            )
        )
        body = harness.chat("Ajoute une tâche").json()
        assert body["reply"] is None
        assert body["pending_action"] == {
            "kind": "create_task",
            "internship_id": "stage-1",
            "internship_subject": "Agent IA de suivi",
            "title": "Préparer la démo",
            "due_date": "2026-10-30",
            "description": "",
        }
        assert harness.apis["jeton-encadrant"].created == []

    def test_confirmation_creates_the_task(self, harness: Harness) -> None:
        thread_id = self.propose(harness)
        harness.script(say("C'est fait : la tâche « Préparer la démo » est créée."))

        body = harness.decide(thread_id, approved=True).json()

        assert body["reply"] == "C'est fait : la tâche « Préparer la démo » est créée."
        assert body["tools_used"] == ["proposer_tache"]
        assert harness.apis["jeton-encadrant"].created == [
            {
                "internship_id": "stage-1",
                "title": "Préparer la démo",
                "description": "Démo de fin de sprint",
                "due_date": "2026-10-30",
            }
        ]

    def test_refusal_creates_nothing_and_informs_the_model(self, harness: Harness) -> None:
        thread_id = self.propose(harness)
        harness.script(say("D'accord, je n'ai rien créé."))

        body = harness.decide(thread_id, approved=False).json()

        assert body["reply"] == "D'accord, je n'ai rien créé."
        assert harness.apis["jeton-encadrant"].created == []
        assert "refusé" in str(harness.model.received[-1][-1].content)

    def test_the_api_still_has_the_last_word(self, harness: Harness) -> None:
        harness.script(
            call("proposer_tache", stage_id="stage-1", titre="Démo", echeance="2026-10-30"),
            say("L'API a refusé : seul l'encadrant du stage peut créer une tâche."),
        )
        thread_id = harness.chat("Ajoute une tâche", token="jeton-autre").json()["thread_id"]
        body = harness.decide(thread_id, approved=True, token="jeton-autre").json()

        assert "refusé" in body["reply"]
        assert "403" in str(harness.model.received[-1][-1].content)

    def test_only_the_author_can_decide(self, harness: Harness) -> None:
        thread_id = self.propose(harness)
        assert harness.decide(thread_id, approved=True, token="jeton-rh").status_code == 404
        assert harness.apis["jeton-encadrant"].created == []

    def test_deciding_without_pending_action_is_rejected(self, harness: Harness) -> None:
        harness.script(say("Bonjour."))
        thread_id = harness.chat("Bonjour").json()["thread_id"]
        response = harness.decide(thread_id, approved=True)
        assert response.status_code == 409
        assert response.json()["type"].endswith("/no-pending-action")


class TestFailures:
    def test_missing_token(self, harness: Harness) -> None:
        response = harness.client.post("/api/v1/agent/chat", json={"message": "Bonjour"})
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.headers["Content-Type"] == "application/problem+json"

    def test_token_rejected_by_the_api(self, harness: Harness) -> None:
        assert harness.chat("Bonjour", token="jeton-expire").status_code == 401

    def test_message_is_validated(self, harness: Harness) -> None:
        assert harness.chat("   ").status_code == 422
        response = harness.chat("x" * 2001)
        assert response.status_code == 422
        assert response.json()["errors"][0]["location"] == ["body", "message"]

    def test_the_model_cannot_loop_forever(self, harness: Harness) -> None:
        harness.script(*[call("lister_stages") for _ in range(10)])
        body = harness.chat("Liste les stages").json()
        assert "reformuler" in body["reply"]

    def test_model_unavailable(self, harness: Harness) -> None:
        harness.script(ConnectionError("Ollama ne répond pas"))
        response = harness.chat("Bonjour")
        assert response.status_code == 503
        assert "Ollama" in response.json()["detail"]

    def test_api_unreachable(self, harness: Harness) -> None:
        def unreachable(name: str) -> None:
            raise ApiUnreachableError("connexion refusée")

        harness.api_for("jeton-encadrant").on_call = unreachable
        harness.script(call("lister_stages"))
        response = harness.chat("Liste les stages")
        assert response.status_code == 502
        assert response.json()["type"].endswith("/api-unreachable")

    def test_unexpected_api_error(self, harness: Harness) -> None:
        def failing_me() -> Me:
            raise ApiCallError(500, "Erreur interne")

        harness.api_for("jeton-encadrant").me = failing_me  # type: ignore[method-assign]
        response = harness.chat("Bonjour")
        assert response.status_code == 502
        assert "500" in response.json()["detail"]


def test_health(harness: Harness) -> None:
    assert harness.client.get("/health/live").json() == {"status": "ok"}
