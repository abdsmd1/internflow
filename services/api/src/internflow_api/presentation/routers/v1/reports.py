"""Routes des rapports hebdomadaires."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from internflow_api.application.report_search import (
    MAX_RESULTS,
    QUERY_MAX_LENGTH,
    QUERY_MIN_LENGTH,
    SearchReports,
    SearchReportsQuery,
)
from internflow_api.application.reports import (
    ListReports,
    ReviewReport,
    SubmitReport,
    SubmitReportCommand,
)
from internflow_api.domain.internship import InternshipId
from internflow_api.domain.report import IsoWeek, ReportId
from internflow_api.presentation.dependencies import (
    list_reports_use_case,
    review_report_use_case,
    search_reports_use_case,
    submit_report_use_case,
)
from internflow_api.presentation.schemas.reports import (
    ReportCreate,
    ReportRead,
    ReportReview,
    ReportSearchHit,
)
from internflow_api.presentation.security import ActorDep

router = APIRouter(tags=["Rapports hebdomadaires"])


@router.post(
    "/internships/{internship_id}/reports",
    status_code=status.HTTP_201_CREATED,
    summary="Déposer le rapport de la semaine (stagiaire)",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Stage introuvable"},
        status.HTTP_409_CONFLICT: {
            "description": "Rapport déjà déposé pour cette semaine, ou stage pas en cours"
        },
    },
)
def submit_report(
    internship_id: UUID,
    payload: ReportCreate,
    actor: ActorDep,
    use_case: Annotated[SubmitReport, Depends(submit_report_use_case)],
) -> ReportRead:
    report = use_case.execute(
        actor,
        SubmitReportCommand(
            internship_id=InternshipId(internship_id),
            week=IsoWeek.parse(payload.week),
            accomplishments=payload.accomplishments,
            difficulties=payload.difficulties,
            next_steps=payload.next_steps,
        ),
    )
    return ReportRead.from_entity(report)


@router.get(
    "/internships/{internship_id}/reports",
    summary="Lister les rapports d'un stage (semaine la plus récente d'abord)",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Stage introuvable"}},
)
def list_reports(
    internship_id: UUID,
    actor: ActorDep,
    use_case: Annotated[ListReports, Depends(list_reports_use_case)],
) -> list[ReportRead]:
    return [ReportRead.from_entity(r) for r in use_case.execute(actor, InternshipId(internship_id))]


@router.post(
    "/reports/{report_id}/review",
    summary="Relire un rapport et laisser un retour (encadrant du stage ou RH)",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Rapport introuvable"},
        status.HTTP_409_CONFLICT: {"description": "Rapport déjà relu"},
    },
)
def review_report(
    report_id: UUID,
    payload: ReportReview,
    actor: ActorDep,
    use_case: Annotated[ReviewReport, Depends(review_report_use_case)],
) -> ReportRead:
    return ReportRead.from_entity(use_case.execute(actor, ReportId(report_id), payload.feedback))


@router.get(
    "/reports/search",
    summary="Recherche sémantique dans les rapports visibles par l'appelant",
    description=(
        "Retrouve les passages de rapports dont le **sens** est proche de la question, "
        "même sans mot commun. Les droits habituels s'appliquent : un encadrant ne "
        "cherche que dans les stages qu'il encadre, un stagiaire dans les siens."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Stage introuvable (filtre `internship_id`)"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Modèle d'embeddings indisponible (RFC 9457)"
        },
    },
)
def search_reports(
    actor: ActorDep,
    use_case: Annotated[SearchReports, Depends(search_reports_use_case)],
    q: Annotated[
        str,
        Query(
            min_length=QUERY_MIN_LENGTH,
            max_length=QUERY_MAX_LENGTH,
            description="Question ou thème recherché.",
            examples=["difficultés avec Docker"],
        ),
    ],
    internship_id: Annotated[UUID | None, Query(description="Limiter à un stage.")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_RESULTS)] = 5,
) -> list[ReportSearchHit]:
    hits = use_case.execute(
        actor,
        SearchReportsQuery(
            text=q,
            internship_id=InternshipId(internship_id) if internship_id else None,
            limit=limit,
        ),
    )
    return [ReportSearchHit.from_hit(h) for h in hits]
