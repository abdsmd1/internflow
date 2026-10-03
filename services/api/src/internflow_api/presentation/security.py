"""Identification de l'appelant à partir de l'en-tête `Authorization: Bearer <jeton>`.

Le schéma OAuth2 « password » active le bouton **Authorize** de Swagger UI.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from internflow_api.domain.exceptions import InvalidTokenError
from internflow_api.domain.ports.security import TokenService
from internflow_api.domain.user import Principal

TOKEN_URL = "/api/v1/auth/token"  # noqa: S105 (une URL, pas un secret)

# auto_error=False : l'absence de jeton est traitée par nos propres erreurs (RFC 9457).
_bearer = OAuth2PasswordBearer(tokenUrl=TOKEN_URL, auto_error=False)


def get_token_service(request: Request) -> TokenService:
    service: TokenService = request.app.state.token_service
    return service


def get_current_principal(
    token: Annotated[str | None, Depends(_bearer)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> Principal:
    if not token:
        raise InvalidTokenError
    return tokens.decode(token)


ActorDep = Annotated[Principal, Depends(get_current_principal)]
