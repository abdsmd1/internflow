from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from internflow_api.domain.authorization import (
    ensure_can_cancel_internship,
    ensure_can_progress_internship,
    ensure_can_view_intern,
    ensure_can_view_internship,
    require_role,
    scope_internship_filter,
)
from internflow_api.domain.exceptions import (
    InternNotFoundError,
    InternshipNotFoundError,
    PermissionDeniedError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipStatus
from internflow_api.domain.ports.repositories import InternshipFilter
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.user import Principal, Role, UserId

SARA, AMINE = InternId(uuid4()), InternId(uuid4())
KARIM, NADIA = SupervisorId(uuid4()), SupervisorId(uuid4())

HR = Principal(UserId(uuid4()), Role.HR)
KARIM_ACCOUNT = Principal(UserId(uuid4()), Role.SUPERVISOR, supervisor_id=KARIM)
NADIA_ACCOUNT = Principal(UserId(uuid4()), Role.SUPERVISOR, supervisor_id=NADIA)
SARA_ACCOUNT = Principal(UserId(uuid4()), Role.INTERN, intern_id=SARA)
AMINE_ACCOUNT = Principal(UserId(uuid4()), Role.INTERN, intern_id=AMINE)

SARA_WITH_KARIM = Internship.plan(
    intern_id=SARA,
    supervisor_id=KARIM,
    subject="Agent IA",
    period=DateRange(date(2026, 10, 5), date(2027, 2, 5)),
    now=datetime(2026, 10, 1, tzinfo=UTC),
)


class TestRequireRole:
    def test_allowed(self) -> None:
        require_role(HR, Role.HR)

    def test_denied(self) -> None:
        with pytest.raises(PermissionDeniedError):
            require_role(SARA_ACCOUNT, Role.HR, Role.SUPERVISOR)


class TestInternVisibility:
    @pytest.mark.parametrize("actor", [HR, KARIM_ACCOUNT, SARA_ACCOUNT])
    def test_visible(self, actor: Principal) -> None:
        ensure_can_view_intern(actor, SARA)

    def test_intern_cannot_see_another_intern(self) -> None:
        with pytest.raises(InternNotFoundError):
            ensure_can_view_intern(AMINE_ACCOUNT, SARA)


class TestInternshipVisibility:
    @pytest.mark.parametrize("actor", [HR, KARIM_ACCOUNT, SARA_ACCOUNT])
    def test_visible_to_hr_and_participants(self, actor: Principal) -> None:
        ensure_can_view_internship(actor, SARA_WITH_KARIM)

    @pytest.mark.parametrize("actor", [NADIA_ACCOUNT, AMINE_ACCOUNT])
    def test_hidden_from_others_as_not_found(self, actor: Principal) -> None:
        with pytest.raises(InternshipNotFoundError):
            ensure_can_view_internship(actor, SARA_WITH_KARIM)


class TestFilterScoping:
    def test_hr_filter_is_untouched(self) -> None:
        criteria = InternshipFilter(intern_id=AMINE, status=InternshipStatus.PLANNED)
        assert scope_internship_filter(HR, criteria) == criteria

    def test_supervisor_is_restricted_to_own_internships(self) -> None:
        scoped = scope_internship_filter(KARIM_ACCOUNT, InternshipFilter(supervisor_id=NADIA))
        assert scoped.supervisor_id == KARIM

    def test_intern_is_restricted_to_own_internships(self) -> None:
        scoped = scope_internship_filter(
            SARA_ACCOUNT, InternshipFilter(intern_id=AMINE, status=InternshipStatus.ONGOING)
        )
        assert (scoped.intern_id, scoped.status) == (SARA, InternshipStatus.ONGOING)


class TestInternshipActions:
    @pytest.mark.parametrize("actor", [HR, KARIM_ACCOUNT])
    def test_hr_and_own_supervisor_can_progress(self, actor: Principal) -> None:
        ensure_can_progress_internship(actor, SARA_WITH_KARIM)

    def test_intern_cannot_progress_own_internship(self) -> None:
        with pytest.raises(PermissionDeniedError):
            ensure_can_progress_internship(SARA_ACCOUNT, SARA_WITH_KARIM)

    def test_other_supervisor_does_not_even_see_it(self) -> None:
        with pytest.raises(InternshipNotFoundError):
            ensure_can_progress_internship(NADIA_ACCOUNT, SARA_WITH_KARIM)

    def test_only_hr_can_cancel(self) -> None:
        ensure_can_cancel_internship(HR, SARA_WITH_KARIM)
        for actor in (KARIM_ACCOUNT, SARA_ACCOUNT):
            with pytest.raises(PermissionDeniedError):
                ensure_can_cancel_internship(actor, SARA_WITH_KARIM)
