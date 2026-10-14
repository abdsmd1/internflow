"""Cas d'usage de la recherche sémantique dans les rapports (RAG).

- `ReportIndexer` : (ré)indexe un rapport dans la même transaction que son
  enregistrement, pour que l'index reflète toujours les données.
- `SearchReports` : retrouve les passages les plus proches d'une question,
  **uniquement** dans les stages que l'appelant a le droit de voir.
- `ReindexReports` : reconstruit tout l'index (données importées, changement de modèle).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import structlog

from internflow_api.application.internships import load_visible_internship
from internflow_api.domain.authorization import scope_internship_filter
from internflow_api.domain.exceptions import InvalidValueError
from internflow_api.domain.internship import InternshipId
from internflow_api.domain.ports.repositories import IndexedPassage, InternshipFilter
from internflow_api.domain.ports.search import EmbeddingUnavailableError, TextEmbedder
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.report import WeeklyReport
from internflow_api.domain.report_search import SearchHit, split_into_passages
from internflow_api.domain.user import Principal

logger = structlog.get_logger(__name__)

QUERY_MIN_LENGTH = 2
QUERY_MAX_LENGTH = 500
MAX_RESULTS = 20


class ReportIndexer:
    def __init__(self, embedder: TextEmbedder) -> None:
        self._embedder = embedder

    def index(self, uow: UnitOfWork, report: WeeklyReport) -> int:
        """Calcule les vecteurs du rapport et remplace ses passages dans l'index.

        À appeler dans le bloc `with uow`, avant `commit()`. Renvoie le nombre de
        passages ; lève `EmbeddingUnavailableError` si le modèle ne répond pas.
        """
        passages = split_into_passages(report)
        vectors = self._embedder.embed_passages([p.text_to_embed for p in passages])
        model = self._embedder.model_name
        uow.passages.replace_for_report(
            report.id,
            [IndexedPassage(p, v, model) for p, v in zip(passages, vectors, strict=True)],
        )
        return len(passages)

    def index_if_available(self, uow: UnitOfWork, report: WeeklyReport) -> None:
        """Comme `index`, mais une panne du modèle ne bloque pas l'action métier.

        Déposer ou relire un rapport compte plus que sa recherche : le rapport est
        enregistré, et `reindex-reports` rattrapera l'index plus tard.
        """
        try:
            self.index(uow, report)
        except EmbeddingUnavailableError as error:
            logger.warning("report_not_indexed", report_id=str(report.id), reason=str(error))


@dataclass(frozen=True, slots=True)
class SearchReportsQuery:
    text: str
    internship_id: InternshipId | None = None
    limit: int = 5


class SearchReports:
    def __init__(self, uow: UnitOfWork, embedder: TextEmbedder, min_score: float) -> None:
        self._uow = uow
        self._embedder = embedder
        self._min_score = min_score

    def execute(self, actor: Principal, query: SearchReportsQuery) -> Sequence[SearchHit]:
        text = query.text.strip()
        if not QUERY_MIN_LENGTH <= len(text) <= QUERY_MAX_LENGTH:
            raise InvalidValueError(
                f"La recherche doit faire entre {QUERY_MIN_LENGTH} et "
                f"{QUERY_MAX_LENGTH} caractères."
            )
        limit = max(1, min(query.limit, MAX_RESULTS))
        # Le vecteur est calculé hors transaction : aucune connexion n'est
        # immobilisée pendant le calcul.
        vector = self._embedder.embed_query(text)
        with self._uow as uow:
            if query.internship_id is not None:
                load_visible_internship(uow, actor, query.internship_id)  # sinon : 404
            return uow.passages.search(
                vector,
                scope_internship_filter(actor, InternshipFilter()),
                internship_id=query.internship_id,
                limit=limit,
                min_score=self._min_score,
            )


@dataclass(frozen=True, slots=True)
class ReindexResult:
    reports: int
    passages: int


class ReindexReports:
    """Reconstruit l'index de tous les rapports, par lots (une transaction par lot)."""

    def __init__(self, uow: UnitOfWork, embedder: TextEmbedder, *, batch_size: int = 100) -> None:
        self._uow = uow
        self._indexer = ReportIndexer(embedder)
        self._batch_size = batch_size

    def execute(self) -> ReindexResult:
        with self._uow as uow:
            report_ids = list(uow.reports.list_ids())
        passages = 0
        for start in range(0, len(report_ids), self._batch_size):
            with self._uow as uow:
                for report_id in report_ids[start : start + self._batch_size]:
                    report = uow.reports.get(report_id)
                    if report is None:  # supprimé entre-temps
                        continue
                    passages += self._indexer.index(uow, report)
                uow.commit()
            logger.info("reindex_progress", done=min(start + self._batch_size, len(report_ids)))
        return ReindexResult(reports=len(report_ids), passages=passages)
