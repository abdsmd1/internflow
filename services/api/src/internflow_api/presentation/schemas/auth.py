"""DTO HTTP de l'authentification et des comptes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from internflow_api.application.users import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from internflow_api.domain.user import Principal, Role, User


class TokenResponse(BaseModel):
    """Format de réponse OAuth2 (RFC 6749, §5.1)."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (type de jeton, pas un secret)
    expires_in: int = Field(description="Durée de validité du jeton, en secondes.")


class MeRead(BaseModel):
    user_id: UUID
    role: Role
    intern_id: UUID | None
    supervisor_id: UUID | None

    @classmethod
    def from_principal(cls, principal: Principal) -> MeRead:
        return cls(
            user_id=principal.user_id,
            role=principal.role,
            intern_id=principal.intern_id,
            supervisor_id=principal.supervisor_id,
        )


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(examples=["karim.benali@example.com"])
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        examples=["une-phrase-de-passe-longue"],
        json_schema_extra={"writeOnly": True, "format": "password"},
    )
    role: Role
    intern_id: UUID | None = Field(default=None, description="Obligatoire pour le rôle intern.")
    supervisor_id: UUID | None = Field(
        default=None, description="Obligatoire pour le rôle supervisor."
    )


class UserRead(BaseModel):
    """Le mot de passe et son empreinte ne sortent jamais de l'API."""

    id: UUID
    email: str
    role: Role
    intern_id: UUID | None
    supervisor_id: UUID | None
    is_active: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> UserRead:
        return cls(
            id=user.id,
            email=user.email.value,
            role=user.role,
            intern_id=user.intern_id,
            supervisor_id=user.supervisor_id,
            is_active=user.is_active,
            created_at=user.created_at,
        )
