"""Recherche sémantique : indexation, droits d'accès et réindexation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest

from internflow_api.application.interns import RegisterIntern, RegisterInternCommand
from internflow_api.application.internships import (
    ChangeInternshipStatus,
    InternshipAction,
    PlanInternship,
    PlanInternshipCommand,
)
from internflow_api.application.report_search import (
    ReindexReports,
    ReportIndexer,
    SearchReports,
    SearchReportsQuery,
)
from internflow_api.application.reports import ReviewReport, SubmitReport, SubmitReportCommand
from internflow_api.application.supervisors import RegisterSupervisor, RegisterSupervisorCommand
from internflow_api.domain.exceptions import InternshipNotFoundError, InvalidValueError
from internflow_api.domain.internship import InternshipId
from internflow_api.domain.ports.search import EmbeddingUnavailableError
from internflow_api.domain.report import IsoWeek
from internflow_api.domain.report_search import ReportSection
from internflow_api.domain.user import Principal, Role, UserId
from internflow_api.domain.value_objects import StudyLevel
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from tests.factories import HR, FakeClock
from tests.fake_embedder import KeywordEmbedder

WEEK = IsoWeek(2026, 40)


@dataclass
class Stage:
    internship: InternshipId
    intern: Principal
    supervisor: Principal


@dataclass
class World:
    uow: InMemoryUnitOfWork
    clock: FakeClock
    embedder: KeywordEmbedder
    sara: Stage  # stage « Docker » encadré par Karim
    amine: Stage  # stage « Spark » encadré par Nadia

    def submit(self, stage: Stage, accomplishments: str, difficulties: str = "") -> None:
        SubmitReport(self.uow, self.clock, ReportIndexer(self.embedder)).execute(
            stage.intern,
            SubmitReportCommand(stage.internship, WEEK, accomplishments, difficulties),
        )

    def search(self, actor: Principal, text: str, **options: object) -> list[str]:
        hits = SearchReports(self.uow, self.embedder, min_score=0.3).execute(
            actor,
            SearchReportsQuery(text, **options),  # type: ignore[arg-type]
        )
        return [h.passage.content for h in hits]


def _stage(uow: InMemoryUnitOfWork, clock: FakeClock, name: str) -> Stage:
    intern = RegisterIntern(uow, clock).execute(
        HR, RegisterInternCommand(name, "Test", f"{name}@example.com", "ENSA", StudyLevel.INGENIEUR)
    )
    supervisor = RegisterSupervisor(uow, clock).execute(
        HR, RegisterSupervisorCommand("Enc", name, f"enc.{name}@example.com", "IA")
    )
    internship = PlanInternship(uow, clock).execute(
        HR,
        PlanInternshipCommand(
            intern.id, supervisor.id, "Sujet", date(2026, 10, 1), date(2027, 2, 28)
        ),
    )
    ChangeInternshipStatus(uow, clock).execute(HR, internship.id, InternshipAction.START)
    return Stage(
        internship.id,
        Principal(UserId(uuid4()), Role.INTERN, intern_id=intern.id),
        Principal(UserId(uuid4()), Role.SUPERVISOR, supervisor_id=supervisor.id),
    )


@pytest.fixture
def world(uow: InMemoryUnitOfWork, clock: FakeClock) -> World:
    w = World(
        uow, clock, KeywordEmbedder(), _stage(uow, clock, "sara"), _stage(uow, clock, "amine")
    )
    w.submit(w.sara, "Conteneurisation de l'API.", "Problème de réseau entre conteneurs Docker.")
    w.submit(w.amine, "Pipeline Spark en place.", "Problème de mémoire avec Spark.")
    return w


class TestPermissions:
    def test_hr_searches_every_report(self, world: World) -> None:
        assert len(world.search(HR, "problème")) == 2

    def test_a_supervisor_only_finds_the_reports_of_their_interns(self, world: World) -> None:
        assert world.search(world.sara.supervisor, "problème") == [
            "Problème de réseau entre conteneurs Docker."
        ]
        assert world.search(world.sara.supervisor, "Spark mémoire") == []

    def test_an_intern_only_finds_their_own_reports(self, world: World) -> None:
        found = world.search(world.amine.intern, "Spark")
        assert sorted(found) == ["Pipeline Spark en place.", "Problème de mémoire avec Spark."]
        assert world.search(world.amine.intern, "Docker conteneurs") == []

    def test_filtering_on_an_invisible_internship_is_not_found(self, world: World) -> None:
        with pytest.raises(InternshipNotFoundError):
            world.search(world.sara.supervisor, "Spark", internship_id=world.amine.internship)

    def test_hr_can_restrict_the_search_to_one_internship(self, world: World) -> None:
        found = world.search(HR, "problème", internship_id=world.amine.internship)
        assert found == ["Problème de mémoire avec Spark."]


class TestSearch:
    def test_results_are_sorted_by_relevance(self, world: World) -> None:
        hits = SearchReports(world.uow, world.embedder, min_score=0.0).execute(
            HR, SearchReportsQuery("réseau Docker conteneurs")
        )
        assert hits[0].passage.content == "Problème de réseau entre conteneurs Docker."
        assert hits[0].passage.section is ReportSection.DIFFICULTIES
        assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)

    def test_weak_matches_are_discarded(self, world: World) -> None:
        strict = SearchReports(world.uow, world.embedder, min_score=0.99)
        assert strict.execute(HR, SearchReportsQuery("réseau")) == []

    def test_the_number_of_results_is_capped(self, world: World) -> None:
        everything = SearchReports(world.uow, world.embedder, min_score=-1)
        assert len(everything.execute(HR, SearchReportsQuery("problème", limit=1))) == 1
        assert len(everything.execute(HR, SearchReportsQuery("problème", limit=500))) == 4

    @pytest.mark.parametrize("text", ["", " a ", "x" * 501])
    def test_the_question_must_have_a_reasonable_length(self, world: World, text: str) -> None:
        with pytest.raises(InvalidValueError):
            world.search(HR, text)

    def test_search_fails_cleanly_when_the_model_is_down(self, world: World) -> None:
        world.embedder.available = False
        with pytest.raises(EmbeddingUnavailableError):
            world.search(HR, "Docker")


class TestIndexing:
    def test_the_supervisor_feedback_becomes_searchable(self, world: World) -> None:
        [report] = world.uow.reports.list_for_internship(world.sara.internship)
        ReviewReport(world.uow, world.clock, ReportIndexer(world.embedder)).execute(
            world.sara.supervisor, report.id, "Penser à documenter Kubernetes."
        )
        assert world.search(HR, "Kubernetes") == ["Penser à documenter Kubernetes."]

    def test_a_model_outage_does_not_block_the_report(self, world: World) -> None:
        lina = _stage(world.uow, world.clock, "lina")
        world.embedder.available = False
        world.submit(lina, "Travail sur GraphQL.")  # aucune exception
        world.embedder.available = True

        assert len(world.uow.reports.list_for_internship(lina.internship)) == 1
        assert world.search(HR, "GraphQL") == []  # pas encore indexé…

        result = ReindexReports(world.uow, world.embedder, batch_size=1).execute()

        assert (result.reports, result.passages) == (3, 5)
        assert world.search(HR, "GraphQL") == ["Travail sur GraphQL."]  # …rattrapé

    def test_reindexing_is_idempotent(self, world: World) -> None:
        reindex = ReindexReports(world.uow, world.embedder)
        reindex.execute()
        reindex.execute()
        assert len(world.search(HR, "problème")) == 2  # pas de doublons
