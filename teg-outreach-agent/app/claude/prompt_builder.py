"""Assemble the prompts sent to the `claude` CLI.

Split of responsibility, following the skills-as-prompt-assets pattern:

* **`SKILL.md` + its references** hold the durable instructions — voice, the
  no-invented-facts rules, what not to promise. Editable by a non-engineer.
* **This module** holds the per-prospect data — who they are, what they said,
  which peers may be named, which package applies.

Field-by-field output requirements stay here rather than in the skill, because
they must track `app/domain/schemas.py`; the JSON Schema is what actually
enforces them.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.claude.skill_loader import SkillContent
from app.domain.schemas import IntakeResult, Persona, ResearchDossier


@dataclass(frozen=True)
class BuiltPrompt:
    system_prompt: str
    user_prompt: str


def render_skill(skill: SkillContent) -> str:
    parts = [skill.instructions]
    for name, body in skill.references.items():
        parts.append(f"\n---\n\n<!-- reference: {name} -->\n\n{body}")
    return "\n".join(parts)


def build_proposal_prompt(
    *,
    skill: SkillContent,
    intake: IntakeResult,
    dossier: ResearchDossier,
    persona: Persona,
    transcript: list[dict],
    learned_facts: dict,
    peers: list[str],
    testimonials: list[dict],
    industries: list[str],
    sector_peer_count: int,
    scale_note: str,
    package_line: str,
    session_ref: str,
    version: int,
    price_requested: bool,
    goals: str = "",
    mechanism: str = "",
    evidence: str = "",
    base_pain_pairs: list[tuple[str, str]] | None = None,
) -> BuiltPrompt:
    company = intake.company_name_canonical
    sector = dossier.sector or "their sector"

    convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript) or "(no messages yet)"
    pain_lines = "\n".join(f"- {p} -> {a}" for p, a in (base_pain_pairs or [])) or "(use the pain library above)"
    testi = "\n".join(
        f'- {t["name"]} ({t["role"]}): "{t["quote"]}"' for t in testimonials
    ) or "(none cleared — do not quote anyone)"

    price_rule = (
        package_line
        if price_requested
        else f"{package_line}\nPricing was NOT requested: state NO figures anywhere in the proposal."
    )

    user = f"""\
Write the TEG 2026 proposal for this prospect.

## Who this is for
Person: {intake.person_name}
Company: {company}
Sector: {sector}
Persona: {persona}
Company facts: {dossier.company_profile}
Person facts: {dossier.person_profile}
Learned in the conversation: {learned_facts}

## The conversation so far
{convo}

## TEG facts you may use
Goals: {goals}
Mechanism: {mechanism}
Evidence: {evidence}
Scale note (use verbatim, do not alter the numbers): {scale_note!r}
TEG's 18 official buyer industries: {industries}
Companies in the '{sector}' sector at TEG 2024 (total): {sector_peer_count}

## Peer companies you may name (ONLY these)
{peers}

## Cleared testimonials (at most 2, verbatim, correctly attributed)
{testi}

## Base pain points for this persona (personalize, keep 2-4)
{pain_lines}

## Package
{price_rule}

## Fields to produce
- what_you_told_us: their situation in their own terms, from the conversation.
- pains: 2-4 {{pain, teg_answer}}, personalized from the base set above.
- lead_generation: how TEG generates leads for a company like theirs.
- proof: KB-grounded evidence bullets.
- executive_summary: 3-4 sentences (their role + company, their goal, why TEG
  fits, the headline recommendation).
- how_a_teg_plays_out: 3-6 bullets walking the 3 days, tuned to their goal.
- roi_framing: a value paragraph with NO numbers and NO promised outcomes —
  phrase it "if a single engagement covers the investment many times over".
- sector_fit: 4-6 {{lever, weight}} rows; weight 1-5 = how much each TEG lever
  matters for the '{sector}' sector.
- peers_in_sector_total: echo the integer {sector_peer_count} exactly.
- peer_context_line: ONE sentence giving the named peers context, e.g.
  "{sector_peer_count} companies in {sector} exhibited at TEG 2024 — including
  the names below." Empty string if the count is 0 or there are no named peers.
- target_industries: 3-6 of the 18 official buyer industries above, names
  copied EXACTLY, most-relevant first. Empty list if there is no signal.
- target_industries_note: one sentence on why those industries matter for
  them. No numbers, no promised outcomes. Empty if the list is empty.
- next_steps: concrete actions, including the booking link.
- contact: leave as the TEG contact if you have nothing better.

## Landing-page copy
- hero_headline: 6-12 words naming the outcome for {company}. No numbers.
- hero_subline: one sentence expanding the headline.
- closing_cta_headline: a short line for the final call-to-action.
- closing_cta_body: 1-2 sentences pushing the reader to act. No numbers.
- section_ctas: short button labels for keys 'priorities', 'charts',
  'investment'.

## Echo these exactly
generated_on='__DATE__', session_ref='{session_ref}', version={version},
company='{company}', person='{intake.person_name}', persona='{persona}'

Return only the JSON the schema requires.
"""

    return BuiltPrompt(system_prompt=render_skill(skill), user_prompt=user)
