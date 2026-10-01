"""Traduction entre entités du domaine et enregistrements SQL (pattern Data Mapper)."""

from __future__ import annotations

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel
from internflow_api.infrastructure.persistence.orm import InternRecord


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
