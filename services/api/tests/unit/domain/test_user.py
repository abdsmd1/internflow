from datetime import UTC, datetime
from uuid import uuid4

import pytest

from internflow_api.domain.exceptions import InvalidValueError
from internflow_api.domain.intern import InternId
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.user import Role, User
from internflow_api.domain.value_objects import Email

NOW = datetime(2026, 10, 1, tzinfo=UTC)
INTERN = InternId(uuid4())
SUPERVISOR = SupervisorId(uuid4())


def make_user(role: Role, **overrides: object) -> User:
    fields: dict[str, object] = {
        "email": Email("compte@example.com"),
        "password_hash": "$argon2id$fake",
        "role": role,
        "created_at": NOW,
    }
    fields.update(overrides)
    return User(**fields)  # type: ignore[arg-type]


class TestProfileConsistency:
    @pytest.mark.parametrize(
        ("role", "links"),
        [
            (Role.HR, {}),
            (Role.SUPERVISOR, {"supervisor_id": SUPERVISOR}),
            (Role.INTERN, {"intern_id": INTERN}),
        ],
    )
    def test_valid_combinations(self, role: Role, links: dict[str, object]) -> None:
        assert make_user(role, **links).role is role

    @pytest.mark.parametrize(
        ("role", "links"),
        [
            (Role.HR, {"intern_id": INTERN}),
            (Role.SUPERVISOR, {}),
            (Role.SUPERVISOR, {"intern_id": INTERN}),
            (Role.INTERN, {}),
            (Role.INTERN, {"intern_id": INTERN, "supervisor_id": SUPERVISOR}),
        ],
    )
    def test_invalid_combinations(self, role: Role, links: dict[str, object]) -> None:
        with pytest.raises(InvalidValueError, match="Profil incohérent"):
            make_user(role, **links)

    def test_password_hash_is_required(self) -> None:
        with pytest.raises(InvalidValueError):
            make_user(Role.HR, password_hash="")


class TestPrincipal:
    def test_principal_carries_role_and_profile(self) -> None:
        user = make_user(Role.INTERN, intern_id=INTERN)
        principal = user.to_principal()
        assert (principal.user_id, principal.role, principal.intern_id) == (
            user.id,
            Role.INTERN,
            INTERN,
        )
        assert principal.supervisor_id is None
