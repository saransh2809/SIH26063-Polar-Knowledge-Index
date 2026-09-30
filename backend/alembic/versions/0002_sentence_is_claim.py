"""draft_sentences.is_claim

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("draft_sentences", sa.Column("is_claim", sa.Boolean(), server_default="true", nullable=False))


def downgrade() -> None:
    op.drop_column("draft_sentences", "is_claim")
