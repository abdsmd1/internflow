"""Traduction entre entités du domaine et enregistrements SQL (pattern Data Mapper)."""

from __future__ import annotations

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipId, InternshipStatus
from internflow_api.domain.report import IsoWeek, ReportId, ReportStatus, WeeklyReport
from internflow_api.domain.supervisor import Supervisor, SupervisorId
from internflow_api.domain.task import Task, TaskId, TaskStatus
from internflow_api.domain.user import Role, User, UserId
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel
from internflow_api.infrastructure.persistence.orm import (
    InternRecord,
    InternshipRecord,
    SupervisorRecord,
    TaskRecord,
    UserRecord,
    WeeklyReportRecord,
)


def intern_to_record(intern: Intern) -> InternRecord:
    return InternRecord(
        id=intern.id,
        first_name=intern.name.first_name,
        last_name=intern.name.last_name,
        email=intern.email.value,
        school=intern.school,
        study_level=intern.study_level.value,
        created_at=intern.created_at,
    )


def record_to_intern(record: InternRecord) -> Intern:
    return Intern(
        id=InternId(record.id),
        name=PersonName(record.first_name, record.last_name),
        email=Email(record.email),
        school=record.school,
        study_level=StudyLevel(record.study_level),
        created_at=record.created_at,
    )


def supervisor_to_record(supervisor: Supervisor) -> SupervisorRecord:
    return SupervisorRecord(
        id=supervisor.id,
        first_name=supervisor.name.first_name,
        last_name=supervisor.name.last_name,
        email=supervisor.email.value,
        department=supervisor.department,
        max_interns=supervisor.max_interns,
        created_at=supervisor.created_at,
    )


def record_to_supervisor(record: SupervisorRecord) -> Supervisor:
    return Supervisor(
        id=SupervisorId(record.id),
        name=PersonName(record.first_name, record.last_name),
        email=Email(record.email),
        department=record.department,
        max_interns=record.max_interns,
        created_at=record.created_at,
    )


def internship_to_record(internship: Internship) -> InternshipRecord:
    record = InternshipRecord(id=internship.id, created_at=internship.created_at)
    update_internship_record(record, internship)
    return record


def update_internship_record(record: InternshipRecord, internship: Internship) -> None:
    record.intern_id = internship.intern_id
    record.supervisor_id = internship.supervisor_id
    record.subject = internship.subject
    record.start_date = internship.period.start
    record.end_date = internship.period.end
    record.status = internship.status.value


def record_to_internship(record: InternshipRecord) -> Internship:
    return Internship(
        id=InternshipId(record.id),
        intern_id=InternId(record.intern_id),
        supervisor_id=SupervisorId(record.supervisor_id),
        subject=record.subject,
        period=DateRange(record.start_date, record.end_date),
        status=InternshipStatus(record.status),
        created_at=record.created_at,
    )


def user_to_record(user: User) -> UserRecord:
    return UserRecord(
        id=user.id,
        email=user.email.value,
        password_hash=user.password_hash,
        role=user.role.value,
        intern_id=user.intern_id,
        supervisor_id=user.supervisor_id,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def record_to_user(record: UserRecord) -> User:
    return User(
        id=UserId(record.id),
        email=Email(record.email),
        password_hash=record.password_hash,
        role=Role(record.role),
        intern_id=InternId(record.intern_id) if record.intern_id else None,
        supervisor_id=SupervisorId(record.supervisor_id) if record.supervisor_id else None,
        is_active=record.is_active,
        created_at=record.created_at,
    )


def task_to_record(task: Task) -> TaskRecord:
    record = TaskRecord(id=task.id, created_by=task.created_by, created_at=task.created_at)
    update_task_record(record, task)
    return record


def update_task_record(record: TaskRecord, task: Task) -> None:
    record.internship_id = task.internship_id
    record.title = task.title
    record.description = task.description
    record.due_date = task.due_date
    record.status = task.status.value
    record.completed_at = task.completed_at


def record_to_task(record: TaskRecord) -> Task:
    return Task(
        id=TaskId(record.id),
        internship_id=InternshipId(record.internship_id),
        title=record.title,
        description=record.description,
        due_date=record.due_date,
        status=TaskStatus(record.status),
        created_by=UserId(record.created_by),
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


def report_to_record(report: WeeklyReport) -> WeeklyReportRecord:
    record = WeeklyReportRecord(id=report.id, submitted_at=report.submitted_at)
    update_report_record(record, report)
    return record


def update_report_record(record: WeeklyReportRecord, report: WeeklyReport) -> None:
    record.internship_id = report.internship_id
    record.iso_year = report.week.year
    record.iso_week = report.week.week
    record.accomplishments = report.accomplishments
    record.difficulties = report.difficulties
    record.next_steps = report.next_steps
    record.status = report.status.value
    record.feedback = report.feedback
    record.reviewed_at = report.reviewed_at


def record_to_report(record: WeeklyReportRecord) -> WeeklyReport:
    return WeeklyReport(
        id=ReportId(record.id),
        internship_id=InternshipId(record.internship_id),
        week=IsoWeek(record.iso_year, record.iso_week),
        accomplishments=record.accomplishments,
        difficulties=record.difficulties,
        next_steps=record.next_steps,
        status=ReportStatus(record.status),
        feedback=record.feedback,
        submitted_at=record.submitted_at,
        reviewed_at=record.reviewed_at,
    )
