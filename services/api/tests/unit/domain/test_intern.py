from datetime import UTC, datetime, timedelta, timezone

import pytest

from internflow_api.domain.exceptions import InvalidValueError
from internflow_api.domain.intern import Intern
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel

NOW = datetime(2026, 10, 1, tzinfo=UTC)


class TestEmail:
    def test_normalizes_case_and_whitespace(self) -> None:
        assert Email("  Sara.ElAmrani@Example.COM ").value == "sara.elamrani@example.com"

    def test_equal_by_value(self) -> None:
        assert Email("a@b.ma") == Email("A@B.MA")

    @pytest.mark.parametrize("raw", ["", "sans-arobase.com", "a@b", "a b@c.ma", "@c.ma"])
    def test_rejects_malformed_addresses(self, raw: str) -> None:
        with pytest.raises(InvalidValueError):
            Email(raw)

    def test_rejects_too_long_address(self) -> None:
        with pytest.raises(InvalidValueError):
            Email("a" * 250 + "@x.ma")


class TestPersonName:
    def test_strips_whitespace(self) -> None:
        name = PersonName("  Sara ", " El Amrani ")
        assert name.full_name == "Sara El Amrani"

    @pytest.mark.parametrize(("first", "last"), [("", "X"), ("X", "   "), ("A" * 101, "X")])
    def test_rejects_invalid_names(self, first: str, last: str) -> None:
        with pytest.raises(InvalidValueError):
            PersonName(first, last)


def make_intern(**overrides: object) -> Intern:
    fields: dict[str, object] = {
        "name": PersonName("Sara", "El Amrani"),
        "email": Email("sara@example.com"),
        "school": "ENSA Oujda",
        "study_level": StudyLevel.INGENIEUR,
        "created_at": NOW,
    }
    fields.update(overrides)
    return Intern(**fields)  # type: ignore[arg-type]


class TestIntern:
    def test_each_intern_gets_a_unique_identity(self) -> None:
        assert make_intern().id != make_intern().id

    def test_equality_is_based_on_identity_not_attributes(self) -> None:
        first, second = make_intern(), make_intern()
        same_identity = make_intern(id=first.id, school="Autre école")
        assert first != second
        assert first == same_identity
        assert len({first, second, same_identity}) == 2

    def test_school_is_required(self) -> None:
        with pytest.raises(InvalidValueError, match="établissement"):
            make_intern(school="   ")

    def test_school_length_is_bounded(self) -> None:
        with pytest.raises(InvalidValueError):
            make_intern(school="x" * 151)

    def test_creation_date_must_be_timezone_aware(self) -> None:
        with pytest.raises(InvalidValueError, match="fuseau"):
            make_intern(created_at=datetime(2026, 10, 1))  # noqa: DTZ001

    def test_creation_date_is_normalized_to_utc(self) -> None:
        paris = timezone(timedelta(hours=2))
        intern = make_intern(created_at=datetime(2026, 10, 1, 11, 0, tzinfo=paris))
        assert intern.created_at == NOW.replace(hour=9)
        assert intern.created_at.tzinfo is UTC

    def test_change_email(self) -> None:
        intern = make_intern()
        intern.change_email(Email("nouveau@example.com"))
        assert intern.email.value == "nouveau@example.com"
