from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.jobs.retention import purge_expired
from app.store.db import Base, SessionLocal, engine
from app.store.models import ChatMessage, ChatSession, Inquiry, ResearchDossierRow


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _make_inquiry(s, *, old: bool) -> Inquiry:
    inq = Inquiry(
        person_name="X", company_name_raw="Y", company_name_canonical="Y",
        consent_status="unknown", intent_hint="unknown", source="t",
    )
    s.add(inq)
    await s.flush()
    d = ResearchDossierRow(inquiry_id=inq.id, company_profile={}, person_profile={},
                           relationship="cold", peer_companies=[], field_confidence={},
                           sources=[], review_flags=[], ask_prospect=[], research_cost={})
    s.add(d)
    await s.flush()
    cs = ChatSession(inquiry_id=inq.id, dossier_id=d.id, cta_status="none")
    s.add(cs)
    await s.flush()
    s.add(ChatMessage(session_id=cs.id, turn_index=0, role="agent", content="hi"))
    await s.flush()
    if old:
        await s.execute(
            text("UPDATE inquiries SET created_at = :ts WHERE id = :id"),
            {"ts": datetime.now(timezone.utc) - timedelta(days=400), "id": inq.id},
        )
    return inq


async def test_purge_removes_old_messages_keeps_inquiry_row():
    async with SessionLocal() as s:
        old = await _make_inquiry(s, old=True)
        fresh = await _make_inquiry(s, old=False)
        await s.commit()

    counts = await purge_expired()
    assert counts["chat_messages"] >= 1

    async with SessionLocal() as s:
        inquiries = (await s.execute(select(Inquiry))).scalars().all()
        assert {i.id for i in inquiries} == {old.id, fresh.id}  # both inquiry rows kept
        msgs = (await s.execute(select(ChatMessage))).scalars().all()
        remaining_sessions = {m.session_id for m in msgs}
        # only the fresh inquiry's messages remain
        fresh_sessions = (await s.execute(
            select(ChatSession.id).where(ChatSession.inquiry_id == fresh.id)
        )).scalars().all()
        assert remaining_sessions <= set(fresh_sessions)
        dossiers = (await s.execute(select(ResearchDossierRow))).scalars().all()
        assert all(d.inquiry_id == fresh.id for d in dossiers)
