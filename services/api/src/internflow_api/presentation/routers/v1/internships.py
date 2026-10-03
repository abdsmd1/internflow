"""Routes `/api/v1/internships`.

Les changements de statut sont des **actions** explicites (POST …/start, …/complete,
…/cancel) plutôt qu'un PATCH du champ `status` : le client exprime une intention
métier, et c'est l'entité qui décide si la transition est permise.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from internflow_api.application.internships import (
    ChangeInternshipStatus,
    GetInternship,
    InternshipAction,
    ListInternships,
    PlanInternship,
    PlanInternshipCommand,
)
from internflow_api.application.pagination import MAX_PAGE_SIZE
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import InternshipId, InternshipStatus
from internflow_api.domain.ports.repositories import InternshipFilter
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.presentation.dependencies import (
    change_internship_status_use_case,
    get_internship_use_case,
    list_internships_use_case,
    plan_internship_use_case,
)
from internflow_api.presentation.schemas.internships import (
    InternshipCreate,
    InternshipPage,
    InternshipRead,
)

router = APIRouter(prefix="/internships", tags=["Stages"])

_NOT_FOUND: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {"description": "Stage introuvable"}
}
_TRANSITION_RESPONSES: dict[int | str, dict[str, object]] = {
    **_NOT_FOUND,
    status.HTTP_409_CONFLICT: {"description": "Transition de statut non autorisée"},
}

ChangeStatusDep = Annotated[ChangeInternshipStatus, Depends(change_internship_status_use_case)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Planifier un stage",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Stagiaire ou encadrant introuvable"},
        status.HTTP_409_CONFLICT: {
            "description": "Chevauchement de stages ou capacité de l'encadrant atteinte"
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Données invalides (RFC 9457)"},
    },
)
def plan_internship(
    payload: InternshipCreate,
    request: Request,
    response: Response,
    use_case: Annotated[PlanInternship, Depends(plan_internship_use_case)],
) -> InternshipRead:
    internship = use_case.execute(
        PlanInternshipCommand(
            intern_id=InternId(payload.intern_id),
            supervisor_id=SupervisorId(payload.supervisor_id),
            subject=payload.subject,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    )
    response.headers["Location"] = request.url_for(
        "get_internship", internship_id=internship.id
    ).path
    return InternshipRead.from_entity(internship)


@router.get("/{internship_id}", summary="Consulter un stage", responses={**_NOT_FOUND})
def get_internship(
    internship_id: UUID,
    use_case: Annotated[GetInternship, Depends(get_internship_use_case)],
) -> InternshipRead:
    return InternshipRead.from_entity(use_case.execute(InternshipId(internship_id)))


@router.get("", summary="Lister les stages (filtres combinables, paginé)")
def list_internships(
    *,  # paramètres nommés uniquement : plus lisible avec de nombreux filtres
    use_case: Annotated[ListInternships, Depends(list_internships_use_case)],
    intern_id: UUID | None = None,
    supervisor_id: UUID | None = None,
    status_filter: Annotated[InternshipStatus | None, Query(alias="status")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> InternshipPage:
    criteria = InternshipFilter(
        intern_id=InternId(intern_id) if intern_id else None,
        supervisor_id=SupervisorId(supervisor_id) if supervisor_id else None,
        status=status_filter,
    )
    return InternshipPage.from_page(use_case.execute(criteria, offset=offset, limit=limit))


@router.post(
    "/{internship_id}/start",
    summary="Démarrer un stage (à partir de sa date de début)",
    responses=_TRANSITION_RESPONSES,
)
def start_internship(internship_id: UUID, use_case: ChangeStatusDep) -> InternshipRead:
    internship = use_case.execute(InternshipId(internship_id), InternshipAction.START)
    return InternshipRead.from_entity(internship)


@router.post(
    "/{internship_id}/complete",
    summary="Terminer un stage en cours",
    responses=_TRANSITION_RESPONSES,
)
def complete_internship(internship_id: UUID, use_case: ChangeStatusDep) -> InternshipRead:
    internship = use_case.execute(InternshipId(internship_id), InternshipAction.COMPLETE)
    return InternshipRead.from_entity(internship)


@router.post(
    "/{internship_id}/cancel",
    summary="Annuler un stage prévu ou en cours",
    responses=_TRANSITION_RESPONSES,
)
def cancel_internship(internship_id: UUID, use_case: ChangeStatusDep) -> InternshipRead:
    internship = use_case.execute(InternshipId(internship_id), InternshipAction.CANCEL)
    return InternshipRead.from_entity(internship)
