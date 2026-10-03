"""Traduction entre entités du domaine et enregistrements SQL (pattern Data Mapper)."""

from __future__ import annotations

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipId, InternshipStatus
from internflow_api.domain.supervisor import Supervisor, SupervisorId
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel
from internflow_api.infrastructure.persistence.orm import (
    InternRecord,
    InternshipRecord,
    SupervisorRecord,
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
