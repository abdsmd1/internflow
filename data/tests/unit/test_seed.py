"""Le générateur produit des données réalistes ET conformes à toutes les règles métier."""

from collections import Counter
from datetime import date

import pytest

from internflow_api.domain.internship import MAX_INTERNSHIP_DAYS, InternshipStatus
from internflow_api.domain.report import IsoWeek
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from internflow_data.seed.generator import (
    DISABLED_PASSWORD_HASH,
    EMAIL_DOMAIN,
    GeneratedData,
    HistoryGenerator,
    SeedConfig,
    persist,
)

TODAY = date(2026, 10, 6)


@pytest.fixture(scope="module")
def data() -> GeneratedData:
    return HistoryGenerator(SeedConfig(supervisors=8, interns=60, seed=7), today=TODAY).generate()


def test_is_deterministic(data: GeneratedData) -> None:
    again = HistoryGenerator(SeedConfig(supervisors=8, interns=60, seed=7), today=TODAY).generate()
    assert [i.email for i in again.interns] == [i.email for i in data.interns]
    assert len(again.tasks) == len(data.tasks)


def test_produces_every_kind_of_status(data: GeneratedData) -> None:
    assert set(Counter(i.status for i in data.internships)) >= {
        InternshipStatus.PLANNED,
        InternshipStatus.ONGOING,
        InternshipStatus.COMPLETED,
    }
    assert {t.status.value for t in data.tasks} == {"todo", "in_progress", "done"}
    assert {r.status.value for r in data.reports} == {"submitted", "reviewed"}


def test_only_fictitious_and_non_loginable_accounts(data: GeneratedData) -> None:
    assert all(i.email.value.endswith(f"@{EMAIL_DOMAIN}") for i in data.interns)
    assert all(u.password_hash == DISABLED_PASSWORD_HASH for u in data.users)


def test_respects_internship_rules(data: GeneratedData) -> None:
    assert all(i.period.days <= MAX_INTERNSHIP_DAYS for i in data.internships)
    assert len({i.intern_id for i in data.internships}) == len(data.internships)


def test_supervisors_never_exceed_capacity(data: GeneratedData) -> None:
    # La charge maximale d'un encadrant est atteinte au début d'un de ses stages :
    # il suffit donc de compter les stages actifs à chacune de ces dates.
    capacity = {s.id: s.max_interns for s in data.supervisors}
    for internship in data.internships:
        day = internship.period.start
        active = [
            other
            for other in data.internships
            if other.supervisor_id == internship.supervisor_id
            and other.period.start <= day <= other.period.end
        ]
        assert len(active) <= capacity[internship.supervisor_id]


def test_nothing_happens_in_the_future(data: GeneratedData) -> None:
    assert all(t.completed_at is None or t.completed_at.date() <= TODAY for t in data.tasks)
    assert all(r.submitted_at.date() <= TODAY for r in data.reports)
    assert all(r.week < IsoWeek.of(TODAY) for r in data.reports)


def test_one_report_per_week(data: GeneratedData) -> None:
    keys = [(r.internship_id, r.week) for r in data.reports]
    assert len(keys) == len(set(keys))


def test_can_be_persisted_atomically(data: GeneratedData) -> None:
    uow = InMemoryUnitOfWork()
    persist(data, uow)
    with uow:
        assert uow.supervisors.list(offset=0, limit=100).total == len(data.supervisors)
