"""Migrate embeddings to pgvector

Revision ID: 8941abc2d3e4
Revises: 75284daa5420
Create Date: 2026-09-12 17:19:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = '8941abc2d3e4'
down_revision: Union[str, Sequence[str], None] = '75284daa5420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Ensure vector extension is enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('ALTER TABLE observations ALTER COLUMN embedding TYPE vector(768) USING (embedding::text::vector)')

def downgrade() -> None:
    op.execute('ALTER TABLE observations ALTER COLUMN embedding TYPE JSON USING (embedding::text::json)')
