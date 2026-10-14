"""Recherche dans les rapports, de bout en bout (HTTP), avec les vrais rôles."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.e2e.stages import API, Stage
from tests.fake_embedder import KeywordEmbedder

SEARCH = f"{API}/reports/search"


def submit(stage: Stage, difficulties: str) -> str:
    response = stage.as_sara().post(
        stage.reports_url,
        json={
            "week": "2026-W40",
            "accomplishments": "Conteneurisation de l'API.",
            "difficulties": difficulties,
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_a_supervisor_finds_a_difficulty_and_its_source(stage: Stage) -> None:
    report_id = submit(stage, "Le réseau entre les conteneurs Docker ne fonctionne pas.")

    response = stage.as_karim().get(SEARCH, params={"q": "problème Docker réseau"})

    assert response.status_code == 200, response.text
    best = response.json()[0]
    assert best == {
        "report_id": report_id,
        "internship_id": stage.internship_id,
        "week": "2026-W40",
        "section": "difficulties",
        "section_label": "Difficultés",
        "excerpt": "Le réseau entre les conteneurs Docker ne fonctionne pas.",
        "score": best["score"],
    }
    assert 0 < best["score"] <= 1


def test_the_supervisor_feedback_is_searchable_after_review(stage: Stage) -> None:
    report_id = submit(stage, "Aucune.")
    reviewed = stage.as_karim().post(
        f"{API}/reports/{report_id}/review", json={"feedback": "Ajouter des tests Playwright."}
    )
    assert reviewed.status_code == 200

    [hit] = stage.as_sara().get(SEARCH, params={"q": "tests Playwright"}).json()
    assert (hit["section"], hit["excerpt"]) == ("feedback", "Ajouter des tests Playwright.")


def test_results_can_be_limited_to_one_internship(stage: Stage) -> None:
    submit(stage, "Docker refuse de démarrer.")
    params: dict[str, str | int] = {"q": "Docker", "internship_id": stage.internship_id, "limit": 1}
    response = stage.as_hr().get(SEARCH, params=params)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_an_unknown_internship_is_not_found(client: TestClient) -> None:
    response = client.get(SEARCH, params={"q": "Docker", "internship_id": str(uuid4())})
    assert response.status_code == 404


def test_the_question_is_validated(client: TestClient) -> None:
    response = client.get(SEARCH, params={"q": "a"})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_authentication_is_required(anonymous_client: TestClient) -> None:
    assert anonymous_client.get(SEARCH, params={"q": "Docker"}).status_code == 401


def test_a_model_outage_is_a_clean_503(client: TestClient, embedder: KeywordEmbedder) -> None:
    embedder.available = False
    response = client.get(SEARCH, params={"q": "Docker"})
    assert response.status_code == 503
    body = response.json()
    assert body["type"].endswith("/search-unavailable")
    assert "hors service" not in body["detail"]  # la cause technique reste dans les logs


def test_a_model_outage_does_not_block_report_submission(
    stage: Stage, embedder: KeywordEmbedder
) -> None:
    embedder.available = False
    submit(stage, "Docker en panne.")  # 201 malgré la panne du modèle
