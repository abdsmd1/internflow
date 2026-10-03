"""Injection de dépendances FastAPI : relie les routes aux cas d'usage.

Les routes ne construisent jamais elles-mêmes un repository ou une session :
elles reçoivent un cas d'usage prêt à l'emploi.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from internflow_api.application.interns import GetIntern, ListInterns, RegisterIntern
from internflow_api.application.internships import (
    ChangeInternshipStatus,
    GetInternship,
    ListInternships,
    PlanInternship,
)
from internflow_api.application.supervisors import (
    GetSupervisor,
    ListSupervisors,
    RegisterSupervisor,
)
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.unit_of_work import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


def get_uow(request: Request) -> UnitOfWork:
    # Une nouvelle unité de travail par requête : aucune session partagée entre threads.
    factory: UnitOfWorkFactory = request.app.state.uow_factory
    return factory()


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ClockDep = Annotated[Clock, Depends(get_clock)]


def register_intern_use_case(uow: UowDep, clock: ClockDep) -> RegisterIntern:
    return RegisterIntern(uow, clock)


def get_intern_use_case(uow: UowDep) -> GetIntern:
    return GetIntern(uow)


def list_interns_use_case(uow: UowDep) -> ListInterns:
    return ListInterns(uow)


# ------------------------------------------------------------------ encadrants
def register_supervisor_use_case(uow: UowDep, clock: ClockDep) -> RegisterSupervisor:
    return RegisterSupervisor(uow, clock)


def get_supervisor_use_case(uow: UowDep) -> GetSupervisor:
    return GetSupervisor(uow)


def list_supervisors_use_case(uow: UowDep) -> ListSupervisors:
    return ListSupervisors(uow)


# ---------------------------------------------------------------------- stages
def plan_internship_use_case(uow: UowDep, clock: ClockDep) -> PlanInternship:
    return PlanInternship(uow, clock)


def get_internship_use_case(uow: UowDep) -> GetInternship:
    return GetInternship(uow)


def list_internships_use_case(uow: UowDep) -> ListInternships:
    return ListInternships(uow)


def change_internship_status_use_case(uow: UowDep, clock: ClockDep) -> ChangeInternshipStatus:
    return ChangeInternshipStatus(uow, clock)
