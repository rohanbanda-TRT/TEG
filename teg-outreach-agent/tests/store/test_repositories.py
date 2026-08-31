# tests/store/test_repositories.py
import pytest

from app.domain.schemas import (
    HandoffPacket, IntakePayload, IntakeResult, PersuasionInit, ResearchDossier,
)
from app.store.db import Base, SessionLocal, engine
from app.store.repositories import (
    DossierRepo, HandoffRepo, InquiryRepo, MessageRepo, SessionRepo,
)


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _intake():
    return IntakeResult(
        person_name="Rohan B", company_name_raw="TRT",
        company_name_canonical="Third Rock Techkno",
        provided_fields=["email"], intent_hint="exhibitor", consent_status="given",
    )


async def test_full_persistence_roundtrip():
    async with SessionLocal() as s:
        inq = await InquiryRepo(s).create(
            IntakePayload(person_name="Rohan B", company_name="TRT", email="r@x.com", consent=True),
            _intake(),
        )
        await s.flush()
        dossier = ResearchDossier(sector="AI", relationship="returning", peer_companies=["NeuraMonks"])
        drow = await DossierRepo(s).create(inq.id, dossier)
        await s.flush()
        cs = await SessionRepo(s).create(
            inq.id, drow.id,
            PersuasionInit(persona="it_tech_service", target_cta="book_stall", opening_message="hi"),
        )
        await s.flush()
        mr = MessageRepo(s)
        await mr.append(cs.id, "agent", "hi", turn_index=await mr.next_turn_index(cs.id))
        await mr.append(cs.id, "prospect", "tell me more", turn_index=await mr.next_turn_index(cs.id))
        await SessionRepo(s).update_state(
            cs.id, cta_status="offered", cta_type=None, cta_detail={}, learned_facts={"x": 1},
            persona="it_tech_service", persona_remapped=False, needs_review=False,
        )
        await HandoffRepo(s).create(cs.id, HandoffPacket(
            summary="s", recommended_next_step="n", suggested_followup_message="m",
            prospect_confidence="high", key_facts={},
        ))
        await SessionRepo(s).finalize(cs.id, outcome_status="contacted", handoff_generated=True)
        await s.commit()

        hist = await MessageRepo(s).history(cs.id)
        assert [m["role"] for m in hist] == ["agent", "prospect"]
        got = await SessionRepo(s).get(cs.id)
        assert got.cta_status == "offered"
        assert got.outcome_status == "contacted"
        assert got.learned_facts == {"x": 1}
        h = await HandoffRepo(s).get_by_session(cs.id)
        assert h.prospect_confidence == "high"
        dom = DossierRepo.to_domain(await DossierRepo(s).get(drow.id))
        assert dom.sector == "AI"
