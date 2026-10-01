"""Sondes de santé pour Docker / Kubernetes.

- live  : le processus répond (sinon → redémarrage du conteneur)
- ready : les dépendances (base de données) sont joignables (sinon → plus de trafic)
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Request, Response, status

router = APIRouter(prefix="/health", tags=["Santé"])

ReadinessCheck = Callable[[], bool]


@router.get("/live", summary="Sonde de vivacité")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Sonde de disponibilité")
def ready(request: Request, response: Response) -> dict[str, str]:
    check: ReadinessCheck = request.app.state.readiness_check
    if check():
        return {"status": "ok"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unavailable"}
