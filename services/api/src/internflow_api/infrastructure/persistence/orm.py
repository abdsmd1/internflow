"""Modèle relationnel SQLAlchemy.

Volontairement séparé de l'entité du domaine : la table peut évoluer
(index, colonnes techniques) sans toucher au modèle métier.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Conventions de nommage explicites : migrations Alembic stables et lisibles.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

INTERN_EMAIL_UNIQUE_CONSTRAINT = "uq_interns_email"


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
