"""Fixtures des tests HTTP."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.e2e.stages import Stage, make_stage


@pytest.fixture
def stage(client: TestClient) -> Stage:
    """Stage EN COURS de Sara, encadrée par Karim (horloge de test : 1er octobre 2026)."""
    return make_stage(client)
