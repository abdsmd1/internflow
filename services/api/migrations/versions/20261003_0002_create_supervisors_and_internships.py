"""Création des tables supervisors et internships.

La contrainte d'exclusion `ex_internships_intern_overlap` garantit, au niveau de
la base, qu'un stagiaire n'a jamais deux stages actifs qui se chevauchent
(voir ADR 0006). Elle nécessite l'extension `btree_gist`.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extension « trusted » depuis PostgreSQL 13 : le propriétaire de la base peut l'activer.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "supervisors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("max_interns", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "max_interns BETWEEN 1 AND 10", name=op.f("ck_supervisors_max_interns_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supervisors")),
        sa.UniqueConstraint("email", name=op.f("uq_supervisors_email")),
    )
    op.create_index(op.f("ix_supervisors_created_at"), "supervisors", ["created_at"])

    op.create_table(
        "internships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("intern_id", sa.Uuid(), nullable=False),
        sa.Column("supervisor_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_date > start_date", name=op.f("ck_internships_period_valid")),
        sa.CheckConstraint(
            "status IN ('planned', 'ongoing', 'completed', 'cancelled')",
            name=op.f("ck_internships_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["intern_id"],
            ["interns.id"],
            name=op.f("fk_internships_intern_id_interns"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supervisor_id"],
            ["supervisors.id"],
            name=op.f("fk_internships_supervisor_id_supervisors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internships")),
    )
    op.create_index(op.f("ix_internships_intern_id"), "internships", ["intern_id"])
    op.create_index(op.f("ix_internships_supervisor_id"), "internships", ["supervisor_id"])
    op.create_index(op.f("ix_internships_status"), "internships", ["status"])
    op.create_index(op.f("ix_internships_created_at"), "internships", ["created_at"])

    op.execute(
        """
        ALTER TABLE internships
        ADD CONSTRAINT ex_internships_intern_overlap
        EXCLUDE USING gist (
            intern_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        )
        WHERE (status IN ('planned', 'ongoing'))
        """
    )


def downgrade() -> None:
    op.drop_table("internships")  # supprime aussi ses index et contraintes
    op.drop_index(op.f("ix_supervisors_created_at"), table_name="supervisors")
    op.drop_table("supervisors")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
