"""Render a ResearchDossier into a human-readable "Company Research Brief".

Built ONLY from fields already present on the dossier — no new research
calls, no LLM call, no invented content. Every section is deterministic
string formatting; a section with nothing to say states that plainly
(e.g. "Not enough public signal to assess") rather than being omitted or
padded with generic filler.
"""
from __future__ import annotations

from app.domain.schemas import ResearchDossier

_NOT_ENOUGH_SIGNAL = "Not enough public signal to assess."

_RELATIONSHIP_LINE = {
    "insider": "This company has an insider relationship with TEG (an organizer contact).",
    "returning": "This company has prior TEG history (a returning exhibitor, sponsor, or speaker).",
    "cold": "This is a first-time contact — no prior TEG relationship found.",
}


def _profile_line(label: str, value) -> str | None:
    if value in (None, "", [], {}):
        return None
    return f"- **{label}:** {value}"


def _executive_summary(d: ResearchDossier) -> list[str]:
    cp = d.company_profile
    bits: list[str] = []
    if d.sector:
        bits.append(f"operates in the **{d.sector}** sector")
    if cp.get("company_size"):
        bits.append(f"an estimated size of {cp['company_size']}")
    if cp.get("hq"):
        bits.append(f"based in {cp['hq']}")
    summary = ""
    if bits:
        summary = "This company " + ", ".join(bits) + ". "
    summary += _RELATIONSHIP_LINE.get(d.relationship, _RELATIONSHIP_LINE["cold"])
    if d.person_company_match is False:
        summary += (
            " Note: research could not confirm the enquiring person is actually "
            "associated with this company — treat firmographic claims here with caution."
        )
    return ["## Executive Summary", "", summary if bits or d.relationship != "cold" else _NOT_ENOUGH_SIGNAL, ""]


def _company_overview(d: ResearchDossier) -> list[str]:
    cp = d.company_profile
    rows = [
        _profile_line("Sector", d.sector),
        _profile_line("Company size", cp.get("company_size")),
        _profile_line("Headquarters", cp.get("hq")),
        _profile_line("Founder", cp.get("founder")),
        _profile_line("Website", cp.get("website")),
        _profile_line("TEG history", cp.get("teg_history")),
    ]
    rows = [r for r in rows if r]
    out = ["## Company Overview", ""]
    if rows:
        out += rows
        out.append("")
    if cp.get("overview"):
        out += [cp["overview"], ""]
    if not rows and not cp.get("overview"):
        out += [_NOT_ENOUGH_SIGNAL, ""]
    pp = d.person_profile
    person_rows = [
        _profile_line("Enquirer designation", pp.get("designation")),
        _profile_line("Seniority", pp.get("seniority")),
        _profile_line("Technical role", pp.get("is_technical")),
        _profile_line("TEG role", pp.get("teg_role")),
    ]
    person_rows = [r for r in person_rows if r]
    if person_rows or pp.get("background"):
        out += ["**Enquirer:**", ""]
        out += person_rows
        if pp.get("background"):
            out += ["", pp["background"]]
        out.append("")
    return out


def _growth_signals(d: ResearchDossier) -> list[str]:
    """No dedicated growth-metric field exists on ResearchDossier today —
    this reads whatever signal the relationship/history/overview already
    carry, rather than fabricating a trend the research never established."""
    out = ["## Growth Signals", ""]
    cp = d.company_profile
    signals: list[str] = []
    if cp.get("teg_history"):
        signals.append(f"TEG participation history: {cp['teg_history']}.")
    if d.relationship in ("returning", "insider"):
        signals.append(_RELATIONSHIP_LINE[d.relationship])
    if not signals:
        out.append(
            _NOT_ENOUGH_SIGNAL + " Research surfaced no growth trajectory, funding, "
            "or expansion signal for this company."
        )
    else:
        out += [f"- {s}" for s in signals]
    out.append("")
    return out


def _how_they_win_business(d: ResearchDossier) -> list[str]:
    out = ["## How They Currently Win Business", ""]
    overview = d.company_profile.get("overview")
    if overview:
        out += [overview, ""]
    else:
        out += [
            _NOT_ENOUGH_SIGNAL + " No positioning, offering, or go-to-market "
            "description was found for this company.",
            "",
        ]
    return out


def _strengths(d: ResearchDossier) -> list[str]:
    out = ["## Strengths", ""]
    points: list[str] = []
    if d.sector:
        points.append(f"Clear sector fit ({d.sector}) for TEG's buyer audience.")
    if d.relationship in ("returning", "insider"):
        points.append(_RELATIONSHIP_LINE[d.relationship])
    if d.peer_companies:
        points.append(
            f"Sits in a sector with an established TEG peer set "
            f"({len(d.peer_companies)} named peer{'s' if len(d.peer_companies) != 1 else ''} found)."
        )
    if d.company_profile.get("overview"):
        points.append("A public overview/positioning statement was found (see Company Overview).")
    if not points:
        out.append(_NOT_ENOUGH_SIGNAL)
    else:
        out += [f"- {p}" for p in points]
    out.append("")
    return out


def _weaknesses(d: ResearchDossier) -> list[str]:
    """Framed as research gaps / open questions, not invented business
    weaknesses — the dossier has no data source that could honestly
    support a claim about a company's actual weaknesses."""
    out = ["## Weaknesses / Pain Points", "", "*(Framed as research gaps, not claims about the business — the "
           "dossier has no source for actual business weaknesses.)*", ""]
    points: list[str] = []
    if "company_description" in d.ask_prospect:
        points.append("Company identity/description could not be confirmed with confidence — worth asking directly.")
    if "role" in d.ask_prospect:
        points.append("The enquirer's role at the company could not be confirmed with confidence.")
    if "person_company_mismatch" in d.review_flags:
        points.append("Research could not confirm the enquirer is actually associated with this company.")
    if d.kb_confidence_flags:
        points.append(
            "TEG's own facts used in outreach may be stale for this inquiry — flagged: "
            + ", ".join(d.kb_confidence_flags) + "."
        )
    if not points:
        out.append(_NOT_ENOUGH_SIGNAL + " No research gaps were flagged.")
    else:
        out += [f"- {p}" for p in points]
    out.append("")
    return out


def _opportunity_fit(d: ResearchDossier) -> list[str]:
    out = ["## Opportunity Fit for TEG", ""]
    points: list[str] = []
    if d.sector:
        points.append(f"Sector ({d.sector}) matches an active TEG buyer/exhibitor category.")
    if d.peer_companies:
        points.append("Named peer companies already exhibiting: " + ", ".join(d.peer_companies) + ".")
    if d.relationship != "cold":
        points.append(_RELATIONSHIP_LINE[d.relationship])
    if not points:
        out.append(_NOT_ENOUGH_SIGNAL + " No sector, peer, or relationship signal to assess fit.")
    else:
        out += [f"- {p}" for p in points]
    out.append("")
    return out


def _sources(d: ResearchDossier) -> list[str]:
    out = ["## Sources", ""]
    if not d.sources:
        out += [_NOT_ENOUGH_SIGNAL + " No sources were recorded for this research pass.", ""]
        return out
    for s in d.sources:
        loc = s.url or "(knowledge base — no URL)"
        out.append(f"- `{s.field}` — {loc} (tool: {s.tool}, confidence: {s.confidence:.2f})")
    out.append("")
    cost = d.research_cost
    if cost:
        out.append(
            f"*Research cost: {cost.get('web_calls', 0)} web call(s), "
            f"{cost.get('scrape_calls', 0)} scrape(s), {cost.get('llm_calls', 0)} LLM call(s).*"
        )
    return out


def render_company_brief(dossier: ResearchDossier) -> str:
    lines: list[str] = ["# Company Research Brief", ""]
    lines += _executive_summary(dossier)
    lines += _company_overview(dossier)
    lines += _growth_signals(dossier)
    lines += _how_they_win_business(dossier)
    lines += _strengths(dossier)
    lines += _weaknesses(dossier)
    lines += _opportunity_fit(dossier)
    lines += _sources(dossier)
    return "\n".join(lines).rstrip() + "\n"
