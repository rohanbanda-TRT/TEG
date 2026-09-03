"""add chat_sessions.discovery_state

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("discovery_state", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "discovery_state")
