"""Jetons d'accès JWT signés (HS256), à durée de vie courte."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, timedelta
from typing import Any

import jwt

from internflow_api.domain.exceptions import InvalidTokenError
from internflow_api.domain.intern import InternId
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.security import AccessToken
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.user import Principal, Role, UserId

_ALGORITHM = "HS256"
_REQUIRED_CLAIMS = ["sub", "role", "iat", "exp", "iss", "aud", "jti"]
MIN_SECRET_LENGTH = 32


class JwtTokenService:
    """Implémentation du port `TokenService`.

    Bonnes pratiques appliquées :
    - algorithme imposé au décodage (pas d'attaque « alg: none ») ;
    - émetteur (`iss`) et audience (`aud`) vérifiés ;
    - expiration courte, `jti` unique pour une future liste de révocation.
    """

    def __init__(
        self,
        *,
        secret: str,
        clock: Clock,
        ttl: timedelta = timedelta(minutes=30),
        issuer: str = "internflow-api",
        audience: str = "internflow",
    ) -> None:
        if len(secret) < MIN_SECRET_LENGTH:
            raise ValueError(
                f"Le secret JWT doit contenir au moins {MIN_SECRET_LENGTH} caractères."
            )
        self._secret = secret
        self._clock = clock
        self._ttl = ttl
        self._issuer = issuer
        self._audience = audience

    def issue(self, principal: Principal) -> AccessToken:
        now = self._clock.now().astimezone(UTC)
        claims: dict[str, Any] = {
            "sub": str(principal.user_id),
            "role": principal.role.value,
            "iat": now,
            "exp": now + self._ttl,
            "iss": self._issuer,
            "aud": self._audience,
            "jti": uuid.uuid4().hex,
        }
        if principal.intern_id is not None:
            claims["intern_id"] = str(principal.intern_id)
        if principal.supervisor_id is not None:
            claims["supervisor_id"] = str(principal.supervisor_id)
        token = jwt.encode(claims, self._secret, algorithm=_ALGORITHM)
        return AccessToken(value=token, expires_in_seconds=int(self._ttl.total_seconds()))

    def decode(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                # L'expiration est contrôlée juste après avec NOTRE horloge (injectable),
                # ce qui permet de tester l'expiration sans attendre.
                options={"require": _REQUIRED_CLAIMS, "verify_exp": False, "verify_iat": False},
            )
            if int(claims["exp"]) <= int(self._clock.now().timestamp()):
                raise InvalidTokenError
            return Principal(
                user_id=UserId(uuid.UUID(claims["sub"])),
                role=Role(claims["role"]),
                intern_id=_optional_uuid(claims, "intern_id", InternId),
                supervisor_id=_optional_uuid(claims, "supervisor_id", SupervisorId),
            )
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            raise InvalidTokenError from exc


def _optional_uuid[T](claims: dict[str, Any], key: str, kind: Callable[[uuid.UUID], T]) -> T | None:
    return kind(uuid.UUID(claims[key])) if key in claims else None
