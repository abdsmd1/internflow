"""Routes `/api/v1/auth` : obtention d'un jeton et identité courante."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from internflow_api.application.users import Authenticate
from internflow_api.presentation.dependencies import authenticate_use_case
from internflow_api.presentation.schemas.auth import MeRead, TokenResponse
from internflow_api.presentation.security import ActorDep

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post(
    "/token",
    summary="Se connecter (e-mail + mot de passe → jeton d'accès)",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Identifiants incorrects"}},
)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    use_case: Annotated[Authenticate, Depends(authenticate_use_case)],
) -> TokenResponse:
    """Flux OAuth2 « password » : le champ `username` contient l'adresse e-mail."""
    token = use_case.execute(form.username, form.password)
    return TokenResponse(access_token=token.value, expires_in=token.expires_in_seconds)


@router.get(
    "/me",
    summary="Qui suis-je ?",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Jeton absent ou invalide"}},
)
def me(actor: ActorDep) -> MeRead:
    return MeRead.from_principal(actor)
