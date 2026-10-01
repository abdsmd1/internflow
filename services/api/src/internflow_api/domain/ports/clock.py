from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Source du temps injectable : rend les tests déterministes."""

    def now(self) -> datetime: ...
