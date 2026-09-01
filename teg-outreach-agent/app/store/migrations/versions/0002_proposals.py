"""proposals table + chat_messages.attachment

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("attachment", JSONB(), nullable=True))
    op.create_table(
        "proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("proposal_json", JSONB(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("png_path", sa.Text(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("guardrail_flags", JSONB(), nullable=True),
        sa.Column("emailed_to", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("proposals")
    op.drop_column("chat_messages", "attachment")
