from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config.settings import get_settings

HARD_REQUIREMENTS = frozenset({"email", "phone", "consent"})
ENRICHABLE_FIELDS = frozenset({
    "designation", "linkedin_url", "sector", "company_size", "website",
    "prior_teg_involvement",
})


class OutreachConfigError(RuntimeError):
    """Raised when outreach_config.md is missing an expected section/table."""


@dataclass(frozen=True)
class OutreachRules:
    hard_requirements: frozenset[str]
    enrichable_fields: frozenset[str]
    persona_triggers: dict[str, dict]
    confidence_thresholds: dict[str, dict[str, float]]
    guardrails: list[str]


def _config_path() -> Path:
    return Path(get_settings().kb_path).resolve() / "outreach_config.md"


def _require(text: str, heading: str) -> None:
    if heading not in text:
        raise OutreachConfigError(f"outreach_config.md missing expected heading: {heading!r}")


def _percent(cell: str) -> float:
    m = re.search(r"(\d+)\s*%", cell)
    if not m:
        raise OutreachConfigError(f"expected a percentage in {cell!r}")
    return int(m.group(1)) / 100.0


def _parse_thresholds(text: str) -> dict[str, dict[str, float]]:
    # Each subsection's first data row is the auto-accept tier ("95%+"),
    # the second is the review-band lower bound ("70-94%").
    out: dict[str, dict[str, float]] = {}
    blocks = {
        "company_name": "### Company Name Matching",
        "linkedin": "### LinkedIn Profile Matching",
        "sector": "### Sector Classification",
    }
    for key, heading in blocks.items():
        _require(text, heading)
        seg = text.split(heading, 1)[1].split("\n###", 1)[0].split("\n##", 1)[0]
        rows = [r for r in seg.splitlines() if r.strip().startswith("|") and "%" in r]
        if len(rows) < 2:
            raise OutreachConfigError(f"{heading}: expected >=2 data rows with percentages")
        auto = _percent(rows[0])
        review_low = _percent(rows[1])
        out[key] = {"auto_accept": auto, "review_low": review_low}
    return out


def _parse_personas(text: str) -> dict[str, dict]:
    _require(text, "## Persona Mapping Rules")
    seg = text.split("## Persona Mapping Rules", 1)[1].split("\n## ", 1)[0]
    mapping = {
        "it_tech_service": "### IT/Tech Service Company",
        "ai_startup": "### AI/Deep-Tech Startup",
        "non_tech_sponsor": "### Non-Tech Sponsor",
        "visitor": "### Visitor",
    }
    out: dict[str, dict] = {}
    for key, heading in mapping.items():
        if heading not in seg:
            raise OutreachConfigError(f"persona section missing: {heading!r}")
        body = seg.split(heading, 1)[1].split("\n###", 1)[0]
        trigger_line = next(
            (l for l in body.splitlines() if "**Trigger:**" in l), ""
        )
        sectors = re.findall(r"\[([^\]]+)\]", trigger_line)
        sector_list: list[str] = []
        for grp in sectors:
            sector_list.extend(s.strip() for s in grp.split(","))
        size_max = None
        m = re.search(r"size\s*<\s*(\d+)", trigger_line)
        if m:
            size_max = int(m.group(1))
        intent = None
        m = re.search(r'Intent\s*=\s*"(\w+)"', trigger_line)
        if m:
            intent = m.group(1)
        props = [
            l.strip("- ").strip()
            for l in body.splitlines()
            if l.strip().startswith("- ")
        ]
        out[key] = {
            "sectors": sector_list,
            "size_max": size_max,
            "intent": intent,
            "value_props": props,
        }
    return out


def _parse_guardrails(text: str) -> list[str]:
    _require(text, "## Guardrails")
    seg = text.split("## Guardrails", 1)[1].split("\n## ", 1)[0]
    bullets = [
        l.strip("- ").strip()
        for l in seg.splitlines()
        if l.strip().startswith("- ")
    ]
    if not bullets:
        raise OutreachConfigError("## Guardrails section has no bullet points")
    return bullets


def load_rules() -> OutreachRules:
    path = _config_path()
    if not path.is_file():
        raise OutreachConfigError(f"outreach_config.md not found at {path}")
    text = path.read_text(encoding="utf-8")
    for heading in (
        "## Confidence Thresholds",
        "## Field Classification",
        "### Hard Requirements (Never Enrich)",
        "### Enrichable Fields (Can be researched)",
        "## Persona Mapping Rules",
        "## Guardrails",
    ):
        _require(text, heading)
    return OutreachRules(
        hard_requirements=HARD_REQUIREMENTS,
        enrichable_fields=ENRICHABLE_FIELDS,
        persona_triggers=_parse_personas(text),
        confidence_thresholds=_parse_thresholds(text),
        guardrails=_parse_guardrails(text),
    )
