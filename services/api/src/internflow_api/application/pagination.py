"""Règles de pagination partagées par tous les cas d'usage de lecture."""

from __future__ import annotations

MAX_PAGE_SIZE = 100


def clamp_pagination(offset: int, limit: int) -> tuple[int, int]:
    """Défense en profondeur : l'API valide déjà, mais le métier ne fait pas confiance."""
    return max(offset, 0), min(max(limit, 1), MAX_PAGE_SIZE)
