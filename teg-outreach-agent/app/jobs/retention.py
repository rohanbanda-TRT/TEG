from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select

from app.store.db import SessionLocal
from app.store.models import (
    ChatMessage,
    ChatSession,
    HandoffPacketRow,
    Inquiry,
    ProposalRow,
    ResearchDossierRow,
)
from config.settings import get_settings


async def purge_expired(now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=get_settings().data_retention_days)
    counts = {
        "chat_messages": 0, "handoff_packets": 0, "proposals": 0,
        "chat_sessions": 0, "research_dossiers": 0,
    }
    async with SessionLocal() as s:
        old_inq_ids = (await s.execute(
            select(Inquiry.id).where(Inquiry.created_at < cutoff)
        )).scalars().all()
        if not old_inq_ids:
            return counts

        session_ids = (await s.execute(
            select(ChatSession.id).where(ChatSession.inquiry_id.in_(old_inq_ids))
        )).scalars().all()

        if session_ids:
            prows = (await s.execute(
                select(ProposalRow).where(ProposalRow.session_id.in_(session_ids))
            )).scalars().all()
            for pr in prows:
                for path in (pr.pdf_path, pr.png_path):
                    if path:
                        Path(path).unlink(missing_ok=True)
                if pr.pdf_path:
                    try:
                        Path(pr.pdf_path).parent.rmdir()  # only if now empty
                    except OSError:
                        pass
            counts["proposals"] = (await s.execute(
                delete(ProposalRow).where(ProposalRow.session_id.in_(session_ids))
            )).rowcount or 0

            counts["chat_messages"] = (await s.execute(
                delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids))
            )).rowcount or 0
            counts["handoff_packets"] = (await s.execute(
                delete(HandoffPacketRow).where(HandoffPacketRow.session_id.in_(session_ids))
            )).rowcount or 0
            counts["chat_sessions"] = (await s.execute(
                delete(ChatSession).where(ChatSession.id.in_(session_ids))
            )).rowcount or 0

        counts["research_dossiers"] = (await s.execute(
            delete(ResearchDossierRow).where(ResearchDossierRow.inquiry_id.in_(old_inq_ids))
        )).rowcount or 0

        await s.commit()
    return counts


if __name__ == "__main__":
    print(asyncio.run(purge_expired()))
