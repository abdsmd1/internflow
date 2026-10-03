"""Routes `/api/v1/users` : gestion des comptes (RH)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from internflow_api.application.users import CreateUserAccount, RegisterUserCommand
from internflow_api.domain.intern import InternId
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.presentation.dependencies import create_user_account_use_case
from internflow_api.presentation.schemas.auth import UserCreate, UserRead
from internflow_api.presentation.security import ActorDep

router = APIRouter(prefix="/users", tags=["Comptes"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte utilisateur (RH)",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Réservé aux RH"},
        status.HTTP_404_NOT_FOUND: {"description": "Profil stagiaire / encadrant introuvable"},
        status.HTTP_409_CONFLICT: {"description": "E-mail déjà utilisé ou profil déjà lié"},
    },
)
def create_user(
    payload: UserCreate,
    actor: ActorDep,
    use_case: Annotated[CreateUserAccount, Depends(create_user_account_use_case)],
) -> UserRead:
    user = use_case.execute(
        actor,
        RegisterUserCommand(
            email=str(payload.email),
            password=payload.password,
            role=payload.role,
            intern_id=InternId(payload.intern_id) if payload.intern_id else None,
            supervisor_id=SupervisorId(payload.supervisor_id) if payload.supervisor_id else None,
        ),
    )
    return UserRead.from_entity(user)
