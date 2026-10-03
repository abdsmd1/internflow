"""Hachage des mots de passe avec Argon2id (recommandation OWASP)."""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    """Implémentation du port `PasswordHasher`.

    Les paramètres par défaut d'argon2-cffi (64 Mio, 3 passes) suivent les
    recommandations actuelles ; les tests utilisent des paramètres allégés.
    """

    def __init__(self, *, time_cost: int = 3, memory_cost_kib: int = 65_536) -> None:
        self._argon2 = _Argon2(time_cost=time_cost, memory_cost=memory_cost_kib, parallelism=4)
        # Empreinte factice calculée une seule fois : sert à vérifier un mot de passe
        # même quand le compte n'existe pas (temps de réponse constant).
        self._dummy_hash = self._argon2.hash("internflow-timing-equalizer")

    def hash(self, password: str) -> str:
        return self._argon2.hash(password)

    def verify(self, password_hash: str | None, password: str) -> bool:
        try:
            return self._argon2.verify(password_hash or self._dummy_hash, password) and (
                password_hash is not None
            )
        except (VerificationError, InvalidHashError):
            return False
