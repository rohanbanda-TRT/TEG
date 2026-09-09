"""company_briefs: add light/deep staleness tracking + deep findings

Revision ID: 0006
Revises: 0005

Adds light_researched_at (an explicit column the light-brief staleness
check reads, replacing the previous use of updated_at, which onupdate-bumps
on ANY column change and would have let a deep-only write make a stale
light dossier look fresh again), plus depth/deep_findings_json/
deep_researched_at for the background deep-research pass (see
docs/superpowers/specs/2026-09-09-background-deep-research-design.md).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_briefs",
        sa.Column("light_researched_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "company_briefs",
        sa.Column("depth", sa.String(8), nullable=False, server_default="light"),
    )
    op.add_column("company_briefs", sa.Column("deep_findings_json", JSONB(), nullable=True))
    op.add_column(
        "company_briefs",
        sa.Column("deep_researched_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_briefs", "deep_researched_at")
    op.drop_column("company_briefs", "deep_findings_json")
    op.drop_column("company_briefs", "depth")
    op.drop_column("company_briefs", "light_researched_at")
