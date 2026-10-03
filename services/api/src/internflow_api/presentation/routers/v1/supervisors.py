"""Routes `/api/v1/supervisors`."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from internflow_api.application.pagination import MAX_PAGE_SIZE
from internflow_api.application.supervisors import (
    GetSupervisor,
    ListSupervisors,
    RegisterSupervisor,
    RegisterSupervisorCommand,
)
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.presentation.dependencies import (
    get_supervisor_use_case,
    list_supervisors_use_case,
    register_supervisor_use_case,
)
from internflow_api.presentation.schemas.supervisors import (
    SupervisorCreate,
    SupervisorPage,
    SupervisorRead,
)

router = APIRouter(prefix="/supervisors", tags=["Encadrants"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer un encadrant",
    responses={
        status.HTTP_409_CONFLICT: {"description": "E-mail déjà utilisé"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Données invalides (RFC 9457)"},
    },
)
def register_supervisor(
    payload: SupervisorCreate,
    request: Request,
    response: Response,
    use_case: Annotated[RegisterSupervisor, Depends(register_supervisor_use_case)],
) -> SupervisorRead:
    supervisor = use_case.execute(
        RegisterSupervisorCommand(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=str(payload.email),
            department=payload.department,
            max_interns=payload.max_interns,
        )
    )
    response.headers["Location"] = request.url_for(
        "get_supervisor", supervisor_id=supervisor.id
    ).path
    return SupervisorRead.from_entity(supervisor)


@router.get(
    "/{supervisor_id}",
    summary="Consulter un encadrant",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Encadrant introuvable"}},
)
def get_supervisor(
    supervisor_id: UUID,
    use_case: Annotated[GetSupervisor, Depends(get_supervisor_use_case)],
) -> SupervisorRead:
    return SupervisorRead.from_entity(use_case.execute(SupervisorId(supervisor_id)))


@router.get("", summary="Lister les encadrants (paginé)")
def list_supervisors(
    use_case: Annotated[ListSupervisors, Depends(list_supervisors_use_case)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> SupervisorPage:
    return SupervisorPage.from_page(use_case.execute(offset=offset, limit=limit))
