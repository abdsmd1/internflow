"""Index de recherche sémantique des rapports (pgvector).

Active l'extension `vector` et crée la table des passages de rapports avec leur
embedding. Pas d'index approché (HNSW) : voir ADR 0012.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-14 06:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSION = 384  # figé ici : une migration ne dépend pas du code qui évolue


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('report_passages',
    sa.Column('report_id', sa.Uuid(), nullable=False),
    sa.Column('section', sa.String(length=20), nullable=False),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', Vector(dim=EMBEDDING_DIMENSION), nullable=False),
    sa.Column('embedding_model', sa.String(length=200), nullable=False),
    sa.CheckConstraint("section IN ('accomplishments', 'difficulties', 'next_steps', 'feedback')", name=op.f('ck_report_passages_section_valid')),
    sa.CheckConstraint('position >= 0', name=op.f('ck_report_passages_position_positive')),
    sa.ForeignKeyConstraint(['report_id'], ['weekly_reports.id'], name=op.f('fk_report_passages_report_id_weekly_reports'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('report_id', 'section', 'position', name=op.f('pk_report_passages'))
    )


def downgrade() -> None:
    op.drop_table('report_passages')
    op.execute("DROP EXTENSION IF EXISTS vector")
