"""Routes `/api/v1/interns`. Une route = traduire HTTP → commande → réponse."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from internflow_api.application.interns import (
    MAX_PAGE_SIZE,
    GetIntern,
    ListInterns,
    RegisterIntern,
    RegisterInternCommand,
)
from internflow_api.domain.intern import InternId
from internflow_api.presentation.dependencies import (
    get_intern_use_case,
    list_interns_use_case,
    register_intern_use_case,
)
from internflow_api.presentation.schemas.interns import InternCreate, InternPage, InternRead

router = APIRouter(prefix="/interns", tags=["Stagiaires"])

_PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Données invalides (RFC 9457)"},
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Inscrire un stagiaire",
    responses={
        **_PROBLEM_RESPONSES,
        status.HTTP_409_CONFLICT: {"description": "E-mail déjà utilisé"},
    },
)
def register_intern(
    payload: InternCreate,
    request: Request,
    response: Response,
    use_case: Annotated[RegisterIntern, Depends(register_intern_use_case)],
) -> InternRead:
    intern = use_case.execute(
        RegisterInternCommand(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=str(payload.email),
            school=payload.school,
            study_level=payload.study_level,
        )
    )
    # En-tête Location : bonne pratique REST pour une ressource créée (201).
    response.headers["Location"] = request.url_for("get_intern", intern_id=intern.id).path
    return InternRead.from_entity(intern)


@router.get(
    "/{intern_id}",
    summary="Consulter un stagiaire",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Stagiaire introuvable"}},
)
def get_intern(
    intern_id: UUID,
    use_case: Annotated[GetIntern, Depends(get_intern_use_case)],
) -> InternRead:
    return InternRead.from_entity(use_case.execute(InternId(intern_id)))


@router.get("", summary="Lister les stagiaires (paginé)")
def list_interns(
    use_case: Annotated[ListInterns, Depends(list_interns_use_case)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> InternPage:
    return InternPage.from_page(use_case.execute(offset=offset, limit=limit))
