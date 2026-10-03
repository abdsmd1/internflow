"""Tests des adaptateurs de sécurité : ce sont eux qui protègent l'API."""

from __future__ import annotations

import secrets
from datetime import timedelta
from uuid import uuid4

import jwt
import pytest

from internflow_api.domain.exceptions import InvalidTokenError
from internflow_api.domain.intern import InternId
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.user import Principal, Role, UserId
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from internflow_api.infrastructure.security.jwt_tokens import JwtTokenService
from tests.factories import FIXED_NOW, TEST_JWT_SECRET, FakeClock

SARA = Principal(UserId(uuid4()), Role.INTERN, intern_id=InternId(uuid4()))
KARIM = Principal(UserId(uuid4()), Role.SUPERVISOR, supervisor_id=SupervisorId(uuid4()))


class TestArgon2Hasher:
    def test_hash_and_verify(self, hasher: Argon2PasswordHasher) -> None:
        digest = hasher.hash("phrase-de-passe-1")
        assert hasher.verify(digest, "phrase-de-passe-1")
        assert not hasher.verify(digest, "phrase-de-passe-2")

    def test_same_password_gives_different_hashes(self, hasher: Argon2PasswordHasher) -> None:
        """Sel aléatoire : deux comptes au même mot de passe restent indiscernables."""
        assert hasher.hash("identique-identique") != hasher.hash("identique-identique")

    def test_unknown_account_is_never_accepted(self, hasher: Argon2PasswordHasher) -> None:
        # Même le mot de passe de l'empreinte factice ne doit jamais être accepté.
        assert not hasher.verify(None, "internflow-timing-equalizer")

    def test_corrupted_hash_is_rejected_not_crashing(self, hasher: Argon2PasswordHasher) -> None:
        assert not hasher.verify("pas-une-empreinte", "peu-importe")


class TestJwtTokenService:
    @pytest.fixture
    def clock(self) -> FakeClock:
        return FakeClock()

    @pytest.fixture
    def service(self, clock: FakeClock) -> JwtTokenService:
        return JwtTokenService(secret=TEST_JWT_SECRET, clock=clock, ttl=timedelta(minutes=30))

    @pytest.mark.parametrize("principal", [SARA, KARIM])
    def test_round_trip(self, service: JwtTokenService, principal: Principal) -> None:
        assert service.decode(service.issue(principal).value) == principal

    def test_token_expires(self, service: JwtTokenService, clock: FakeClock) -> None:
        token = service.issue(SARA).value
        clock._current = FIXED_NOW + timedelta(minutes=31)  # on avance l'horloge
        with pytest.raises(InvalidTokenError):
            service.decode(token)

    def test_token_signed_with_another_secret_is_rejected(
        self, service: JwtTokenService, clock: FakeClock
    ) -> None:
        forged = JwtTokenService(secret=secrets.token_urlsafe(32), clock=clock)
        with pytest.raises(InvalidTokenError):
            service.decode(forged.issue(SARA).value)

    def test_tampered_payload_is_rejected(self, service: JwtTokenService) -> None:
        header, _payload, signature = service.issue(SARA).value.split(".")
        hr_payload = jwt.encode({"role": "hr"}, "x" * 32).split(".")[1]
        with pytest.raises(InvalidTokenError):
            service.decode(f"{header}.{hr_payload}.{signature}")

    def test_unsigned_alg_none_token_is_rejected(self, service: JwtTokenService) -> None:
        unsigned = jwt.encode(
            {"sub": str(uuid4()), "role": "hr", "iss": "internflow-api", "aud": "internflow"},
            key=None,
            algorithm="none",
        )
        with pytest.raises(InvalidTokenError):
            service.decode(unsigned)

    def test_wrong_audience_is_rejected(self, clock: FakeClock) -> None:
        other_app = JwtTokenService(secret=TEST_JWT_SECRET, clock=clock, audience="autre-appli")
        mine = JwtTokenService(secret=TEST_JWT_SECRET, clock=clock)
        with pytest.raises(InvalidTokenError):
            mine.decode(other_app.issue(SARA).value)

    @pytest.mark.parametrize("garbage", ["", "abc", "a.b.c"])
    def test_garbage_is_rejected(self, service: JwtTokenService, garbage: str) -> None:
        with pytest.raises(InvalidTokenError):
            service.decode(garbage)

    def test_short_secret_is_refused_at_startup(self, clock: FakeClock) -> None:
        with pytest.raises(ValueError, match="32 caractères"):
            JwtTokenService(secret="trop-court", clock=clock)
