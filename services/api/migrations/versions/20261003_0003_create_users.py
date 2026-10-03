"""Création de la table users (comptes et rôles).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("intern_id", sa.Uuid(), nullable=True),
        sa.Column("supervisor_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('hr', 'supervisor', 'intern')", name=op.f("ck_users_role_valid")
        ),
        sa.CheckConstraint(
            "(role = 'hr' AND intern_id IS NULL AND supervisor_id IS NULL)"
            " OR (role = 'supervisor' AND intern_id IS NULL AND supervisor_id IS NOT NULL)"
            " OR (role = 'intern' AND intern_id IS NOT NULL AND supervisor_id IS NULL)",
            name=op.f("ck_users_profile_matches_role"),
        ),
        sa.ForeignKeyConstraint(
            ["intern_id"],
            ["interns.id"],
            name=op.f("fk_users_intern_id_interns"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supervisor_id"],
            ["supervisors.id"],
            name=op.f("fk_users_supervisor_id_supervisors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("intern_id", name=op.f("uq_users_intern_id")),
        sa.UniqueConstraint("supervisor_id", name=op.f("uq_users_supervisor_id")),
    )


def downgrade() -> None:
    op.drop_table("users")
