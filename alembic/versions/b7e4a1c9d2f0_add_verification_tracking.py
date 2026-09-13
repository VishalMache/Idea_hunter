"""Add retryable verification tracking.

Revision ID: b7e4a1c9d2f0
Revises: 172c8d468a40
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b7e4a1c9d2f0"
down_revision: Union[str, Sequence[str], None] = "172c8d468a40"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("problems", sa.Column("verification_reason", sa.String(length=100), nullable=True))
    op.add_column("problems", sa.Column("verification_details", sa.JSON(), nullable=True))
    op.add_column("problems", sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"))

def downgrade() -> None:
    op.drop_column("problems", "verification_attempts")
    op.drop_column("problems", "verification_details")
    op.drop_column("problems", "verification_reason")
