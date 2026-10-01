"""Création de la table interns.

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("school", sa.String(length=150), nullable=False),
        sa.Column("study_level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interns")),
        sa.UniqueConstraint("email", name=op.f("uq_interns_email")),
    )
    op.create_index(op.f("ix_interns_created_at"), "interns", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_interns_created_at"), table_name="interns")
    op.drop_table("interns")
