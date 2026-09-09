"""add company_briefs table

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_briefs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_key", sa.String(255), nullable=False, unique=True),
        sa.Column("company_name_canonical", sa.Text(), nullable=False),
        sa.Column("dossier_json", JSONB(), nullable=True),
        sa.Column("brief_markdown", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_company_briefs_company_key", "company_briefs", ["company_key"])


def downgrade() -> None:
    op.drop_index("ix_company_briefs_company_key", table_name="company_briefs")
    op.drop_table("company_briefs")
