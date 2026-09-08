import pytest
from sqlalchemy import select

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


async def test_insert_inquiry_and_related_rows():
    async with SessionLocal() as s:
        inq = Inquiry(
            person_name="Rohan B", company_name_raw="TRT",
            company_name_canonical="Third Rock Techkno",
            consent_status="unknown", intent_hint="exhibitor", source="inquiry_page",
        )
        s.add(inq)
        await s.flush()
        d = ResearchDossierRow(
            inquiry_id=inq.id, company_profile={"sector": "AI"}, person_profile={},
            relationship="returning", sector="AI", peer_companies=["NeuraMonks"],
            field_confidence={}, sources=[], review_flags=[], ask_prospect=[], research_cost={},
        )
        s.add(d)
        await s.flush()
        cs = ChatSession(
            inquiry_id=inq.id, dossier_id=d.id, persona="ai_startup",
            target_cta="catalyst_zone_or_pitch", cta_status="none",
        )
        s.add(cs)
        await s.flush()
        s.add(ChatMessage(session_id=cs.id, turn_index=0, role="agent", content="hi"))
        await s.commit()

        rows = (await s.execute(select(Inquiry))).scalars().all()
        assert len(rows) == 1
        assert rows[0].company_name_canonical == "Third Rock Techkno"
