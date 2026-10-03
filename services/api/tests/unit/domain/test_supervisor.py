from datetime import UTC, datetime

import pytest

from internflow_api.domain.exceptions import InvalidValueError, SupervisorCapacityExceededError
from internflow_api.domain.supervisor import DEFAULT_MAX_INTERNS, Supervisor
from internflow_api.domain.value_objects import Email, PersonName

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def make_supervisor(**overrides: object) -> Supervisor:
    fields: dict[str, object] = {
        "name": PersonName("Karim", "Benali"),
        "email": Email("karim.benali@example.com"),
        "department": "Data & IA",
        "created_at": NOW,
    }
    fields.update(overrides)
    return Supervisor(**fields)  # type: ignore[arg-type]


class TestSupervisor:
    def test_default_capacity(self) -> None:
        assert make_supervisor().max_interns == DEFAULT_MAX_INTERNS

    def test_department_is_required(self) -> None:
        with pytest.raises(InvalidValueError, match="département"):
            make_supervisor(department="  ")

    def test_department_length_is_bounded(self) -> None:
        with pytest.raises(InvalidValueError):
            make_supervisor(department="x" * 101)

    @pytest.mark.parametrize("capacity", [0, -1, 11])
    def test_capacity_must_be_within_bounds(self, capacity: int) -> None:
        with pytest.raises(InvalidValueError, match="capacité"):
            make_supervisor(max_interns=capacity)

    def test_creation_date_must_be_timezone_aware(self) -> None:
        with pytest.raises(InvalidValueError):
            make_supervisor(created_at=datetime(2026, 10, 1))  # noqa: DTZ001

    def test_equality_is_based_on_identity(self) -> None:
        first = make_supervisor()
        assert first == make_supervisor(id=first.id)
        assert first != make_supervisor()
        assert len({first, make_supervisor(id=first.id)}) == 1


class TestCapacityRule:
    def test_accepts_while_below_capacity(self) -> None:
        make_supervisor(max_interns=2).ensure_can_supervise_one_more(current_load=1)

    def test_refuses_when_capacity_is_reached(self) -> None:
        supervisor = make_supervisor(max_interns=2)
        with pytest.raises(SupervisorCapacityExceededError) as error:
            supervisor.ensure_can_supervise_one_more(current_load=2)
        assert error.value.max_interns == 2
