# tests/config/test_outreach_rules.py
import pytest

from config.outreach_rules import (
    load_rules, OutreachRules, OutreachConfigError,
    HARD_REQUIREMENTS, ENRICHABLE_FIELDS,
)


def test_hard_requirements_constant():
    assert HARD_REQUIREMENTS == frozenset({"email", "phone", "consent"})


def test_enrichable_includes_sector_and_linkedin():
    assert "sector" in ENRICHABLE_FIELDS
    assert "linkedin_url" in ENRICHABLE_FIELDS


def test_load_rules_from_real_kb():
    rules = load_rules()
    assert isinstance(rules, OutreachRules)
    # personas
    assert set(rules.persona_triggers) == {
        "it_tech_service", "ai_startup", "non_tech_sponsor", "visitor"
    }
    assert "AI & Machine Learning" in rules.persona_triggers["ai_startup"]["sectors"]
    assert rules.persona_triggers["ai_startup"]["size_max"] == 50
    # thresholds
    assert rules.confidence_thresholds["company_name"]["auto_accept"] == 0.95
    assert rules.confidence_thresholds["sector"]["auto_accept"] == 0.95
    # guardrails carried verbatim
    assert any("fabricated testimonials" in g.lower() for g in rules.guardrails)


def test_load_rules_raises_on_missing_heading(tmp_path, monkeypatch):
    bad = tmp_path / "outreach_config.md"
    bad.write_text("# Outreach Configuration\n\nNo useful sections here.\n")
    monkeypatch.setattr("config.outreach_rules._config_path", lambda: bad)
    with pytest.raises(OutreachConfigError):
        load_rules()
