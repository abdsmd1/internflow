from uuid import uuid4

import pytest

from internflow_api.application.interns import (
    MAX_PAGE_SIZE,
    GetIntern,
    ListInterns,
    RegisterIntern,
    RegisterInternCommand,
)
from internflow_api.domain.exceptions import (
    EmailAlreadyUsedError,
    InternNotFoundError,
    InvalidValueError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.value_objects import StudyLevel
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from tests.factories import FIXED_NOW, FakeClock


def command(**overrides: object) -> RegisterInternCommand:
    fields: dict[str, object] = {
        "first_name": "Sara",
        "last_name": "El Amrani",
        "email": "sara@example.com",
        "school": "ENSA Oujda",
        "study_level": StudyLevel.INGENIEUR,
    }
    fields.update(overrides)
    return RegisterInternCommand(**fields)  # type: ignore[arg-type]


class TestRegisterIntern:
    def test_registers_and_commits(self, uow: InMemoryUnitOfWork, clock: FakeClock) -> None:
        intern = RegisterIntern(uow, clock).execute(command())

        assert uow.committed
        assert intern.created_at == FIXED_NOW
        with uow:
            assert uow.interns.get(intern.id) is not None

    def test_rejects_duplicate_email_case_insensitively(
        self, uow: InMemoryUnitOfWork, clock: FakeClock
    ) -> None:
        use_case = RegisterIntern(uow, clock)
        use_case.execute(command(email="sara@example.com"))

        with pytest.raises(EmailAlreadyUsedError):
            use_case.execute(command(email="SARA@example.com"))

    def test_invalid_data_is_never_persisted(
        self, uow: InMemoryUnitOfWork, clock: FakeClock
    ) -> None:
        with pytest.raises(InvalidValueError):
            RegisterIntern(uow, clock).execute(command(email="invalide"))

        assert ListInterns(uow).execute().total == 0


class TestGetIntern:
    def test_returns_existing_intern(self, uow: InMemoryUnitOfWork, clock: FakeClock) -> None:
        created = RegisterIntern(uow, clock).execute(command())
        assert GetIntern(uow).execute(created.id) == created

    def test_raises_when_missing(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(InternNotFoundError):
            GetIntern(uow).execute(InternId(uuid4()))


class TestListInterns:
    def test_most_recent_first_with_pagination(
        self, uow: InMemoryUnitOfWork, clock: FakeClock
    ) -> None:
        register = RegisterIntern(uow, clock)
        emails = [f"stagiaire{i}@example.com" for i in range(5)]
        for email in emails:
            register.execute(command(email=email))

        page = ListInterns(uow).execute(offset=1, limit=2)

        assert page.total == 5
        assert [i.email.value for i in page.items] == [emails[3], emails[2]]

    @pytest.mark.parametrize(
        ("offset", "limit", "expected_offset", "expected_limit"),
        [(-5, 10, 0, 10), (0, 0, 0, 1), (0, 10_000, 0, MAX_PAGE_SIZE)],
    )
    def test_clamps_pagination_parameters(
        self,
        uow: InMemoryUnitOfWork,
        offset: int,
        limit: int,
        expected_offset: int,
        expected_limit: int,
    ) -> None:
        page = ListInterns(uow).execute(offset=offset, limit=limit)
        assert (page.offset, page.limit) == (expected_offset, expected_limit)
