"""Add source catalog and provenance metadata.

Revision ID: 4c1f0a9e5b12
Revises: 172c8d468a40
"""
from alembic import op
import sqlalchemy as sa
revision = "4c1f0a9e5b12"
down_revision = "172c8d468a40"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sources", sa.Column("categories", sa.JSON(), nullable=True))
    op.add_column("sources", sa.Column("signal_kind", sa.String(length=50), nullable=True))
    op.add_column("sources", sa.Column("acquisition_method", sa.String(length=50), nullable=True))
    op.add_column("sources", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("sources", sa.Column("health_status", sa.String(length=50), nullable=True))
    op.add_column("sources", sa.Column("health_note", sa.Text(), nullable=True))
    op.add_column("observations", sa.Column("metadata_json", sa.JSON(), nullable=True))

def downgrade():
    op.drop_column("observations", "metadata_json")
    op.drop_column("sources", "health_note")
    op.drop_column("sources", "health_status")
    op.drop_column("sources", "enabled")
    op.drop_column("sources", "acquisition_method")
    op.drop_column("sources", "signal_kind")
    op.drop_column("sources", "categories")
