"""Composition root : le SEUL endroit où les adaptateurs concrets sont assemblés.

`create_app` accepte des dépendances optionnelles : en production on branche
PostgreSQL, dans les tests on injecte des adaptateurs en mémoire.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from internflow_api import __version__
from internflow_api.config import Environment, Settings, get_settings
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.security import PasswordHasher, TokenService
from internflow_api.infrastructure.clock import SystemClock
from internflow_api.infrastructure.logging import configure_logging
from internflow_api.infrastructure.persistence.sqlalchemy_uow import (
    SqlAlchemyUnitOfWork,
    build_engine,
)
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from internflow_api.infrastructure.security.jwt_tokens import JwtTokenService
from internflow_api.presentation.dependencies import UnitOfWorkFactory
from internflow_api.presentation.errors import register_exception_handlers
from internflow_api.presentation.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from internflow_api.presentation.routers import health
from internflow_api.presentation.routers.health import ReadinessCheck
from internflow_api.presentation.routers.v1 import (
    auth,
    interns,
    internships,
    reports,
    supervisors,
    tasks,
    users,
)


def _database_readiness(engine: Engine) -> ReadinessCheck:
    def check() -> bool:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    return check


def _sqlalchemy_uow_factory(engine: Engine) -> UnitOfWorkFactory:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return lambda: SqlAlchemyUnitOfWork(session_factory)


def create_app(
    settings: Settings | None = None,
    *,
    uow_factory: UnitOfWorkFactory | None = None,
    clock: Clock | None = None,
    readiness_check: ReadinessCheck | None = None,
    password_hasher: PasswordHasher | None = None,
    token_service: TokenService | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    clock = clock or SystemClock()
    configure_logging(settings.log_level, json=settings.environment is not Environment.LOCAL)

    engine: Engine | None = None
    if uow_factory is None:
        engine = build_engine(
            settings.database_url.unicode_string(), pool_size=settings.database_pool_size
        )
        uow_factory = _sqlalchemy_uow_factory(engine)
        readiness_check = readiness_check or _database_readiness(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            engine.dispose()  # libère proprement le pool de connexions

    app = FastAPI(
        title="InternFlow API",
        version=__version__,
        description="Gestion automatisée des stagiaires.",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    app.state.uow_factory = uow_factory
    app.state.clock = clock
    app.state.readiness_check = readiness_check or (lambda: True)
    app.state.password_hasher = password_hasher or Argon2PasswordHasher()
    app.state.token_service = token_service or JwtTokenService(
        secret=settings.jwt_secret.get_secret_value(),
        clock=clock,
        ttl=timedelta(minutes=settings.access_token_ttl_minutes),
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER, "Location"],
    )
    register_exception_handlers(app)

    # Réponses communes à toutes les routes protégées, documentées dans OpenAPI.
    api_v1 = APIRouter(
        prefix="/api/v1",
        responses={
            401: {"description": "Jeton absent, invalide ou expiré (RFC 9457)"},
            403: {"description": "Action non autorisée pour ce rôle (RFC 9457)"},
        },
    )
    api_v1.include_router(auth.router)
    api_v1.include_router(users.router)
    api_v1.include_router(interns.router)
    api_v1.include_router(supervisors.router)
    api_v1.include_router(internships.router)
    api_v1.include_router(tasks.router)
    api_v1.include_router(reports.router)
    app.include_router(api_v1)
    app.include_router(health.router)
    return app
