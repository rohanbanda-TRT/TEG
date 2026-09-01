from app.kb.loader import GoalsAndPains, KnowledgeBase


def test_goals_and_pains_structure():
    gp = KnowledgeBase().goals_and_pains()
    assert isinstance(gp, GoalsAndPains)
    assert "unified tech stage" in gp.problem.lower() or "fragment" in gp.problem.lower()
    assert set(gp.pains_by_persona) == {
        "it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"
    }


def test_it_service_pains_include_geography():
    gp = KnowledgeBase().goals_and_pains()
    it = gp.pains_by_persona["it_tech_service"]
    assert len(it.pains) >= 3
    joined = " ".join(p + " " + a for p, a in it.pains).lower()
    assert "geograph" in joined or "one geography" in joined or "pipeline" in joined


def test_startup_pains_include_investor_access():
    gp = KnowledgeBase().goals_and_pains()
    joined = " ".join(
        p + " " + a for p, a in gp.pains_by_persona["ai_startup"].pains
    ).lower()
    assert "investor" in joined or "vc" in joined


def test_each_pain_is_a_pair():
    gp = KnowledgeBase().goals_and_pains()
    for pp in gp.pains_by_persona.values():
        for row in pp.pains:
            assert isinstance(row, tuple) and len(row) == 2 and all(row)
