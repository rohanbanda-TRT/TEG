from app.research.tools import ResearchQuery
from app.research.kb_retriever import KBRetriever


async def test_company_hit_populates_fields():
    r = await KBRetriever().lookup(ResearchQuery(
        track="company", subject="Third Rock Techkno", context="Rohan B",
        want=["sector", "website", "teg_history"],
    ))
    assert r.available is True
    assert r.tool_name == "kb"
    assert "AI" in r.fields["sector"]
    assert r.fields["website"].startswith("https://")
    assert "2024" in r.fields["teg_history"]
    assert r.confidence["sector"] == 1.0


async def test_company_miss_returns_unavailable():
    r = await KBRetriever().lookup(ResearchQuery(
        track="company", subject="Zzxqwerty Nonexistent Ltd", context="",
        want=["sector"],
    ))
    assert r.available is False


async def test_person_hit_sets_teg_role():
    r = await KBRetriever().lookup(ResearchQuery(
        track="person", subject="Tejas Shah", context="MagnusMinds",
        want=["role", "teg_role"],
    ))
    assert r.available is True
    assert r.fields["teg_role"] in {"organizer", "founder", "speaker"}
