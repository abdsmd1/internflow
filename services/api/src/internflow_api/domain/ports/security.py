"""Ports de sécurité : le domaine ne sait pas comment on hache ni comment on signe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from internflow_api.domain.user import Principal


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str | None, password: str) -> bool:
        """Vérifie un mot de passe.

        Avec `password_hash=None` (compte inexistant), l'implémentation effectue
        quand même une vérification factice de même durée puis renvoie `False` :
        le temps de réponse ne révèle pas si un e-mail est enregistré.
        """
        ...


@dataclass(frozen=True, slots=True)
class AccessToken:
    value: str
    expires_in_seconds: int


class TokenService(Protocol):
    def issue(self, principal: Principal) -> AccessToken: ...

    def decode(self, token: str) -> Principal:
        """Renvoie l'identité portée par le jeton, ou lève `InvalidTokenError`."""
        ...
