"""Modèle relationnel SQLAlchemy.

Volontairement séparé des entités du domaine : les tables peuvent évoluer
(index, contraintes, colonnes techniques) sans toucher au modèle métier.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Conventions de nommage explicites : migrations Alembic stables et lisibles.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Noms des contraintes que les repositories traduisent en erreurs métier.
INTERN_EMAIL_UNIQUE_CONSTRAINT = "uq_interns_email"
SUPERVISOR_EMAIL_UNIQUE_CONSTRAINT = "uq_supervisors_email"
# Contrainte d'exclusion PostgreSQL (créée dans la migration 0002, voir ADR 0006) :
# deux stages actifs d'un même stagiaire ne peuvent pas se chevaucher.
INTERNSHIP_OVERLAP_CONSTRAINT = "ex_internships_intern_overlap"
USER_EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"
USER_INTERN_UNIQUE_CONSTRAINT = "uq_users_intern_id"
USER_SUPERVISOR_UNIQUE_CONSTRAINT = "uq_users_supervisor_id"
# Un seul rapport par stage et par semaine ISO.
REPORT_WEEK_UNIQUE_CONSTRAINT = "uq_weekly_reports_internship_week"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class InternRecord(Base):
    __tablename__ = "interns"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    school: Mapped[str] = mapped_column(String(150))
    study_level: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SupervisorRecord(Base):
    __tablename__ = "supervisors"
    __table_args__ = (CheckConstraint("max_interns BETWEEN 1 AND 10", name="max_interns_range"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    department: Mapped[str] = mapped_column(String(100))
    max_interns: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class InternshipRecord(Base):
    __tablename__ = "internships"
    __table_args__ = (
        CheckConstraint("end_date > start_date", name="period_valid"),
        CheckConstraint(
            "status IN ('planned', 'ongoing', 'completed', 'cancelled')", name="status_valid"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    # RESTRICT : on ne supprime jamais un stagiaire ou un encadrant qui a un historique de stage.
    intern_id: Mapped[UUID] = mapped_column(
        ForeignKey("interns.id", ondelete="RESTRICT"), index=True
    )
    supervisor_id: Mapped[UUID] = mapped_column(
        ForeignKey("supervisors.id", ondelete="RESTRICT"), index=True
    )
    subject: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('hr', 'supervisor', 'intern')", name="role_valid"),
        # Même règle que l'entité User : le profil lié dépend du rôle.
        CheckConstraint(
            "(role = 'hr' AND intern_id IS NULL AND supervisor_id IS NULL)"
            " OR (role = 'supervisor' AND intern_id IS NULL AND supervisor_id IS NOT NULL)"
            " OR (role = 'intern' AND intern_id IS NOT NULL AND supervisor_id IS NULL)",
            name="profile_matches_role",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    # Un profil a au plus un compte (UNIQUE) ; NULL autorisé pour les autres rôles.
    intern_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interns.id", ondelete="RESTRICT"), unique=True
    )
    supervisor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("supervisors.id", ondelete="RESTRICT"), unique=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskRecord(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="status_valid"),
        CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)", name="completed_at_matches_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    internship_id: Mapped[UUID] = mapped_column(
        ForeignKey("internships.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WeeklyReportRecord(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (
        UniqueConstraint(
            "internship_id", "iso_year", "iso_week", name=REPORT_WEEK_UNIQUE_CONSTRAINT
        ),
        CheckConstraint("iso_week BETWEEN 1 AND 53", name="iso_week_range"),
        CheckConstraint("status IN ('submitted', 'reviewed')", name="status_valid"),
        CheckConstraint(
            "(status = 'reviewed') = (feedback IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="review_matches_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    # Pas d'index dédié : la contrainte UNIQUE (internship_id, iso_year, iso_week)
    # crée déjà un index dont internship_id est la première colonne.
    internship_id: Mapped[UUID] = mapped_column(ForeignKey("internships.id", ondelete="RESTRICT"))
    iso_year: Mapped[int] = mapped_column(SmallInteger)
    iso_week: Mapped[int] = mapped_column(SmallInteger)
    accomplishments: Mapped[str] = mapped_column(Text)
    difficulties: Mapped[str] = mapped_column(Text)
    next_steps: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    feedback: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
