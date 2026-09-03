# KB Growth Content — Gathering Spec

> **Status:** BLOCKING. The growth-first proposal redesign
> (`2026-09-03-growth-first-proposal-design.md`, not yet written) cannot be
> built until this content exists in the KB.
>
> **Owner of the content:** Tapan / the TEG organizers. Not researchable — this
> is TEG's own point of view and track record.
>
> **Owner of the integration:** engineering, once the raw content is delivered.

---

## Why this exists

Feedback on the first generated proposal (Tapan, 3 Sep 2026, voice message):

> "Content बहुत thin है… हमको Tech Expo Gujarat का branding ज्यादा नहीं करना है।
> Itorix अगर stall खरीदती है तो कैसे grow करेगी? क्या business problem solve
> होगा? कौन से clients मिल सकते हैं? Next stage पे कैसे जा सकते हैं? ये सारा
> दिखाना है… देख के लग जाना चाहिए कि मेरे को यहाँ जाना चाहिए।"

The proposal is event-centric ("here is how big TEG is") when it should be
prospect-centric ("here is how *your* business grows if you exhibit").

The KB today supports the *access* argument (who attends, the mechanism, the
scale) but has **none** of:

1. **Outcome stories** — "Company X exhibited, landed client Y, is now Z". The
   company profiles are firmographic snapshots, not before→after.
2. **A next-stage model** — the path an exhibitor takes (first-timer → anchor
   client → local presence → category leader). Nowhere in the KB.
3. **Client archetypes** — the KB says "manufacturing buyers attend". It does
   not say "a high-value client for a software agency is a ₹50–300cr Morbi
   ceramics firm on legacy ERP buying a digital layer".
4. **ROI framing from TEG** — the 4 cleared testimonials speak to scale and
   credibility, not exhibitor ROI (the KB itself flags this).

The prospect-side web-research pass (approved separately) fills some of #3 for
a specific prospect, but cannot supply TEG's track record or TEG's view of the
growth path. That has to be written down.

---

## What to gather

New KB area: **`teg-kb-agent/knowledge_base/exhibitor_growth/`**, four files.

Raw form is fine — bullet points, a dictated transcript, a rough doc.
Engineering cleans it into KB-consistent Markdown, adds it to `INDEX.md`, and
regenerates `facts.json` for anything that needs the deterministic layer (the
outcome stories will — a "cleared stories" allow-list, like the testimonials).

### 1. `growth_paths.md` — TEG's model of how an exhibitor grows

**Ask:** *"When an IT services company like Itorix exhibits at TEG, what does
'success' look like at 3 months? At a year? What's the path — where do they
start, what does a good TEG give them, what does that let them do next? Same
for an AI startup, same for a sponsor."*

**Shape** (guide, not rigid) — per persona:

```
## IT / Tech Service Company
### Stage 1 — First TEG (where most start)
  From:   <typical situation of a company doing its first TEG>
  At TEG: <the specific thing that happens over the 3 days>
  To:     <where they are at the end of the event / first month>
### Stage 2 — <name, e.g. "First anchor client">
  From / At TEG / To
### Stage 3 — <name, e.g. "Local presence">
  From / At TEG / To
```

Personas: `it_tech_service`, `ai_startup`, `non_tech_sponsor`. (Visitors don't
get a proposal, so no visitor path needed.)

### 2. `outcome_stories.md` — real "X exhibited, Y happened"

**Ask:** *"Which past exhibitors got something real out of TEG — a client, a
partnership, a hire, funding? Can we reference it, named or anonymised?"*

**Shape** — 3–6 stories:

```
### <Company or "A 20-person Pune agency"> — <one line: what happened>
  - Before TEG:        <their situation>
  - At TEG:            <which edition, stall size, approach>
  - What came out of it: <client / partnership / hire / funding — concrete>
  - Where they are now: <if known>
  - Cleared for external use: named | anonymised only | not yet cleared
```

Anonymised is usable. The requirement is that TEG **confirms the story is true
and OK to reference** — same bar as the cleared testimonials.

### 3. `client_archetypes.md` — who the high-value buyers actually are

**Ask:** *"For a company selling software / web services, who's the ideal
client walking the TEG floor? Describe them — industry, size, what they're
trying to fix, what a project with them looks like."*

**Shape** — per exhibitor sector, 2–4 archetypes each:

```
## For a Software / Web Development agency
### Archetype: Mid-size manufacturer modernising
  - Who:              <e.g. ₹50–300cr Morbi ceramics / Rajkot engineering /
                       Surat textile firm; family-run; 200–2000 staff;
                       legacy ERP or none>
  - What they need:   <e.g. web presence, B2B commerce, ERP integration,
                       a customer portal>
  - Engagement shape: <e.g. 3–9 month build + follow-on maintenance.
                       NO rupee figure unless TEG is confident of one —
                       an unverified number is worse than none>
  - Roughly how many attend TEG: <"a large share of the 15,000" / a fraction>
### Archetype: <next>
```

Prioritise the sectors most inquiries come from: software/web dev, AI/ML,
digital marketing, enterprise software (ERP/CRM), fintech.

### 4. `roi_framing.md` — how TEG frames the economics, honestly

**Ask:** *"How would you explain the money side to a cautious prospect —
without promising a return?"*

**Shape:**

```
## The exhibitor economics, as TEG frames it
  - What the stall + trip actually costs a small team (honest ballpark)
  - What one good engagement in <sector> is typically worth
  - The break-even logic: "if one conversation becomes one project, then…"
  - What TEG does NOT promise
```

---

## Integration checklist (engineering, after delivery)

- [ ] Clean each file into KB-consistent Markdown (headings, `> Source:` lines,
      `*Last updated:*` footer) matching the style of
      `exhibitor_benefits_analysis.md`.
- [ ] Add all four to `knowledge_base/INDEX.md` under a new
      "Exhibitor Growth" section.
- [ ] `outcome_stories.md`: extract the cleared stories into `facts.json` as a
      `cleared_outcome_stories` list (name, summary, clearance level), the way
      cleared testimonials are handled. Update `scripts/build_kb_facts.py` and
      its `--check` gate.
- [ ] `growth_paths.md`: the proposal writer skill reads this directly via the
      KB explorer — no facts.json entry needed, but confirm the explorer's
      goal string references it by name.
- [ ] Update `scripts/build_skill_references.py` if any of this content should
      be pinned into a `teg-proposal` skill reference file.
- [ ] Re-run `scripts/build_kb_facts.py` and `scripts/build_skill_references.py`,
      commit the regenerated snapshots.

---

## Then: resume the redesign

With this content in place, the growth-first proposal design proceeds:

1. New `teg-proposal` skill — growth-first, drawing on the four files above.
2. New `teg-growth-research` skill — the prospect-side web-research pass.
3. `Proposal` schema → identity fields + `sections: list[Section]`
   (`hero`, `opportunity`, `growth_path`, `clients`, `business_case`,
   `sector_fit`, `proof`, `the_ask`, `custom`).
4. `ProposalAgent.build()` → growth-research call + KB call + one write call
   with a skill-driven self-check (no separate reviewer call, no regex in the
   decision path). Reviewer call added later only if violations slip through.
5. PDF path removed / commented out for now.
6. Landing page rebuilt around a section renderer (component per `kind`).
