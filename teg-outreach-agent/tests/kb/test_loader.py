from app.kb.loader import KnowledgeBase, get_kb, CompanyRecord, PersonRecord


def test_find_company_exact():
    kb = KnowledgeBase()
    rec, score = kb.find_company("Third Rock Techkno")
    assert isinstance(rec, CompanyRecord)
    assert score == 1.0
    assert "AI" in (rec.category or "")
    assert rec.website == "https://www.thirdrocktechkno.com/"
    assert "2024" in (rec.teg_participation or "")


def test_find_company_abbreviation_is_fuzzy_or_miss():
    kb = KnowledgeBase()
    rec, score = kb.find_company("TRT")
    # "TRT" is not the file title; loader must NOT hallucinate a 1.0 match.
    assert score < 0.95


def test_find_company_miss_returns_none():
    kb = KnowledgeBase()
    rec, score = kb.find_company("Zzxqwerty Nonexistent Ltd")
    assert rec is None
    assert score < 0.5


def test_find_person_organizer_and_founder():
    kb = KnowledgeBase()
    rec, score = kb.find_person("Tejas Shah")
    assert isinstance(rec, PersonRecord)
    assert score >= 0.9
    assert rec.kind in {"organizer", "founder"}


def test_peers_in_sector_from_file_only():
    kb = KnowledgeBase()
    peers = kb.peers_in_sector("AI & Machine Learning", limit=5)
    assert "Third Rock Techkno" in peers
    assert "NeuraMonks" in peers
    assert len(peers) <= 5
    # must not include a company absent from that section
    assert "GTPL" not in peers


def test_pricing_has_confirmed_stall_numbers():
    kb = KnowledgeBase()
    p = kb.pricing()
    sizes = {s["size"] for s in p.stalls}
    assert "3m × 3m" in sizes or "3m x 3m" in sizes
    prices = {s["price_inr"] for s in p.stalls}
    assert 117000 in prices
    assert 468000 in prices
    assert p.title_sponsor_inr == 3500000


def test_cleared_testimonials_exactly_four():
    kb = KnowledgeBase()
    t = kb.cleared_testimonials()
    assert len(t) == 4
    names = {x["name"] for x in t}
    assert "Sonu Sharma" in names
    assert "Kanaksinh Rana" in names
    assert all(x["quote"] for x in t)


def test_get_kb_cached():
    assert get_kb() is get_kb()
