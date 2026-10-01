from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Implémentation réelle du port `Clock` : toujours en UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)
