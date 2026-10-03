from uuid import uuid4

import pytest

from internflow_api.application.supervisors import (
    GetSupervisor,
    ListSupervisors,
    RegisterSupervisor,
    RegisterSupervisorCommand,
)
from internflow_api.domain.exceptions import (
    EmailAlreadyUsedError,
    InvalidValueError,
    SupervisorNotFoundError,
)
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from tests.factories import FIXED_NOW, HR, FakeClock


def command(**overrides: object) -> RegisterSupervisorCommand:
    fields: dict[str, object] = {
        "first_name": "Karim",
        "last_name": "Benali",
        "email": "karim.benali@example.com",
        "department": "Data & IA",
    }
    fields.update(overrides)
    return RegisterSupervisorCommand(**fields)  # type: ignore[arg-type]


class TestRegisterSupervisor:
    def test_registers_and_commits(self, uow: InMemoryUnitOfWork, clock: FakeClock) -> None:
        supervisor = RegisterSupervisor(uow, clock).execute(HR, command(max_interns=3))

        assert uow.committed
        assert supervisor.created_at == FIXED_NOW
        assert GetSupervisor(uow).execute(HR, supervisor.id).max_interns == 3

    def test_rejects_duplicate_email(self, uow: InMemoryUnitOfWork, clock: FakeClock) -> None:
        use_case = RegisterSupervisor(uow, clock)
        use_case.execute(HR, command())
        with pytest.raises(EmailAlreadyUsedError):
            use_case.execute(HR, command(email="KARIM.BENALI@example.com"))

    def test_invalid_capacity_is_never_persisted(
        self, uow: InMemoryUnitOfWork, clock: FakeClock
    ) -> None:
        with pytest.raises(InvalidValueError):
            RegisterSupervisor(uow, clock).execute(HR, command(max_interns=0))
        assert ListSupervisors(uow).execute(HR).total == 0


class TestReadSupervisors:
    def test_get_unknown_raises(self, uow: InMemoryUnitOfWork) -> None:
        with pytest.raises(SupervisorNotFoundError):
            GetSupervisor(uow).execute(HR, SupervisorId(uuid4()))

    def test_list_most_recent_first(self, uow: InMemoryUnitOfWork, clock: FakeClock) -> None:
        register = RegisterSupervisor(uow, clock)
        for i in range(3):
            register.execute(HR, command(email=f"enc{i}@example.com"))

        page = ListSupervisors(uow).execute(HR, limit=2)

        assert page.total == 3
        assert [s.email.value for s in page.items] == ["enc2@example.com", "enc1@example.com"]
