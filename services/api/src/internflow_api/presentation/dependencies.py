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
from internflow_api.application.reports import ListReports, ReviewReport, SubmitReport
from internflow_api.application.supervisors import (
    GetSupervisor,
    ListSupervisors,
    RegisterSupervisor,
)
from internflow_api.application.tasks import ChangeTaskStatus, CreateTask, ListTasks
from internflow_api.application.users import Authenticate, CreateUserAccount, RegisterUser
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.security import PasswordHasher, TokenService
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.presentation.security import get_token_service

UnitOfWorkFactory = Callable[[], UnitOfWork]


def get_uow(request: Request) -> UnitOfWork:
    # Une nouvelle unité de travail par requête : aucune session partagée entre threads.
    factory: UnitOfWorkFactory = request.app.state.uow_factory
    return factory()


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def get_password_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.password_hasher
    return hasher


UowDep = Annotated[UnitOfWork, Depends(get_uow)]
ClockDep = Annotated[Clock, Depends(get_clock)]
HasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


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


# ----------------------------------------------------- comptes et authentification
def authenticate_use_case(
    uow: UowDep, hasher: HasherDep, tokens: Annotated[TokenService, Depends(get_token_service)]
) -> Authenticate:
    return Authenticate(uow, hasher, tokens)


def create_user_account_use_case(
    uow: UowDep, clock: ClockDep, hasher: HasherDep
) -> CreateUserAccount:
    return CreateUserAccount(RegisterUser(uow, clock, hasher))


# ---------------------------------------------------------------------- tâches
def create_task_use_case(uow: UowDep, clock: ClockDep) -> CreateTask:
    return CreateTask(uow, clock)


def list_tasks_use_case(uow: UowDep, clock: ClockDep) -> ListTasks:
    return ListTasks(uow, clock)


def change_task_status_use_case(uow: UowDep, clock: ClockDep) -> ChangeTaskStatus:
    return ChangeTaskStatus(uow, clock)


# ------------------------------------------------------------ rapports hebdo
def submit_report_use_case(uow: UowDep, clock: ClockDep) -> SubmitReport:
    return SubmitReport(uow, clock)


def list_reports_use_case(uow: UowDep) -> ListReports:
    return ListReports(uow)


def review_report_use_case(uow: UowDep, clock: ClockDep) -> ReviewReport:
    return ReviewReport(uow, clock)
