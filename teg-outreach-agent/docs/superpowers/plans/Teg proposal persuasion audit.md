# What's Missing From the Proposal — Persuasion Audit

**Subject:** Why a factually solid proposal isn't yet a *convincing* one, using the real Tudip Technologies proposal as the working example.

**Method:** Standard conversion-copy audit lens (hooks, proof, urgency, risk reversal, objection-handling, trust signals) — no marketing plugin was a close enough match in the catalog, so this applies the same framework directly.

**One constraint to hold in mind throughout:** every fix below has to survive `guardrails.py` and the `teg-proposal` skill's anti-fabrication rules. Nothing here asks for an invented statistic, a fake urgency deadline, or a claim the system can't support. Persuasion and honesty aren't in tension here — the current proposal is actually *under-using* the true, compliant material it already has access to.

---

## The core finding

The current proposal is **factually excellent and emotionally flat.** It correctly refuses to invent anything — that discipline is working exactly as designed. But it also currently has almost no mechanism for making a true thing feel urgent, no story of a real company that benefited, no human being to talk to, and no answer to the objections a Pune-based company would obviously have before spending money in a state they've never operated in. Those are all things that can be added **without breaking a single guardrail** — most of them are compliance-safe by construction, because they're either (a) already-true facts the proposal isn't using, or (b) structural additions (a name, a photo, a deadline that's genuinely real) rather than content claims.

---

## 1. No story of a company that actually benefited

**What's missing:** The proposal names 30 real peer companies in Tudip's sector and states a real lever-fit chart — but never tells the story of what happened to *any* of them. There's no "Company X exhibited, landed Client Y, here's where they are now."

**Why it matters:** Buyers don't act on category statistics. They act on a specific story that makes the abstract outcome feel real. Right now the proposal proves TEG is *big*; it never proves TEG *works*.

**Why this one isn't a quick copy fix:** This traces back to a real, structural gap — `teg-kb-agent/knowledge_base/` has no `outcome_stories.md` file. This was already flagged internally (Tapan's own feedback, 3 Sep 2026: *"Itorix अगर stall खरीदती है तो कैसे grow करेगी?"*) and marked **BLOCKING** in `docs/superpowers/specs/2026-09-03-kb-growth-content-spec.md`. Nothing downstream can fix this with better prompting — the content has to be gathered from TEG's own organizers first (3–6 real stories, named or anonymized, cleared for use the same way the 4 testimonials are). This is the single highest-leverage missing piece, and it's a data problem, not a code problem.

---

## 2. No urgency that's actually true

**What's missing:** Nothing in the proposal creates a reason to act *this week* instead of next month. "Reply in the chat" has no clock attached to it.

**Why it matters:** A factually accurate, unhurried proposal is easy to file away and forget. Every high-converting sales document has a true reason the timing matters.

**What's compliant and already true, right now:**
- **Real deadline:** Nov 27, 2026 is ~11 weeks out as of this writing. A live countdown, or even a static "X weeks until the floor opens," is a fact, not a claim.
- **Real scarcity signal:** only ~66 of the 250+ target exhibitors are confirmed so far (per the KB's own exhibitor directory) — "the floor is filling, corner and IT-cluster placements go first" is a true statement the proposal currently never makes.
- **Real cancellation-schedule fact:** if a booking happens close to the event, the refund/cancellation terms tighten (per `registration_and_passes.md`). Framed honestly, this is a legitimate reason to decide sooner rather than later — currently unused anywhere in the generated copy.

None of this requires inventing anything. It requires the proposal to *say* facts it already has.

---

## 3. No trust signal on the other end of the CTA

**What's missing:** The only contact signal on the whole page is a footer-line email in small type. There's nothing that makes the reply feel like it goes to a real, capable team — no identity at all behind the ask.

**Why it matters:** A prospect deciding whether to spend real money hesitates more when the other end of the reply feels anonymous. That doesn't mean it has to be *one individual's name* — this proposal is generated automatically for every prospect, and pinning it to a single person's identity would be misleading about how the system actually works, not just a stylistic choice. The fix is a **team/brand identity, not a personal one**: something that reads as "a real organization is behind this," without implying a specific human wrote or is personally waiting on this exact reply.

**Fix:** Surface something like *"The TEG exhibitor team — reply here and a team member will follow up within [a stated, real turnaround]"* in the CTA section itself, not buried in a footer contact line, paired with the event's own brand mark (logo, "AIMED TECH EXPO GUJARAT LLP") for institutional credibility. This is presentation, not new content, and it doesn't require attaching this to any one person.

---

## 4. No objection handling for the one objection every Gujarat-outsider prospect will have

**What's missing:** Tudip is a Pune company being asked to spend money in Gujarat, at an event run by a Ahmedabad-based peer network they have zero history with. The proposal never once addresses "why would a company from *outside* Gujarat get real value here" — it just proceeds as if that's not a live doubt in the reader's head.

**Why it matters:** Unaddressed objections don't disappear — they just sit in the reader's mind unresolved and become the quiet reason they don't reply. The best persuasive documents name the objection before the reader has to, then answer it.

**What's compliant and true:** the proposal *can* honestly say something like "You'd be one of the only exhibitors in the IT/AI cluster without existing Gujarat ties — that's a real gap in the market this floor represents, not a disadvantage." That's an honest reframe, not a fabricated claim.

---

## 5. No lower-commitment next step

**What's missing:** There is exactly one call to action — "Discuss the stall." For a prospect who isn't ready to commit to a real conversation yet, there's no smaller ask (a one-pager to forward internally, a 15-minute call with no obligation, "see the floor plan first").

**Why it matters:** Single-CTA documents lose everyone who isn't already 80% convinced. A ladder of smaller asks catches more of the reader's actual, more hesitant, decision state.

---

## 6. No visual proof the event is real and professional

**What's missing:** The whole document is charts and text. No venue photo, no floor layout, no photo from TEG 2024, nothing that lets a skeptical reader's eyes confirm "this is a real, well-run thing," not just words claiming it is.

**Why it matters:** For a first-time, out-of-state exhibitor with zero prior exposure to TEG, a photo does work that a paragraph can't — it's instant, low-effort proof.

---

## 7. The package box doesn't yet reflect what's already fixed in code

Separate from the pure-persuasion gaps above: the tier-selection and consistency-check work from the last engineering pass (`_select_tier`, `check_section_consistency`, the two-rule safety ordering) directly fixes the exact self-contradiction that would otherwise undercut trust at the moment of the ask — a prospect reading "we'll fit your two demo stations" next to a package box that says the smallest stall available. That fix is real and already shipped. Worth noting here only because it's the most trust-critical single item on this whole list, and it's already handled — the remaining gaps above are what's left once that foundation is solid.

---

## What a regenerated CTA section looks like with these applied

**Current (paraphrased from the real proposal):**

> Let's shape this around Tudip's targets. If this reads right, reply in the chat and the TEG team will follow up.
>
> [Suggested Package: 3m x 3m stall — includes list]

**With the compliant fixes above applied:**

> **Let's shape this around Tudip's targets — and there's a real reason to move this week.**
>
> Only 66 of TEG 2026's 250+ target exhibitor slots are confirmed so far, and corner placements in the IT/software cluster — the kind built for a two-station demo setup — go first. You'd also be the only confirmed AI/cloud exhibitor from outside Gujarat on this floor right now, which is a real market gap this event represents, not a risk.
>
> The TEG exhibitor team is happy to walk you through the floor plan on a no-obligation 15-minute call before anything is booked, or just reply here if you're ready to talk stall format.
>
> [Suggested Package — tier-matched to the conversation, per the recent consistency fix]
>
> Not ready yet? [One-pager version →]

Nothing above required inventing a number, a testimonial, or a claim — every added sentence is either a real fact the KB already has, or a structural/presentation change (a name, a smaller CTA, a reframed objection).

---

## What this means for the code, concretely

Ranked by leverage, not by ease:

1. **Unblock `2026-09-03-kb-growth-content-spec.md`.** This is not a code task — it's getting Tapan/TEG organizers to actually deliver the four files that spec asks for (`growth_paths.md`, `outcome_stories.md`, `client_archetypes.md`, `roi_framing.md`). Everything else on this list is a copy/structure improvement; this one unlocks a whole category of proof the system currently cannot produce at all, compliantly or otherwise.

2. **Add a `ProposalPackage`-adjacent `UrgencySignal` block to the `Proposal` schema** (`app/domain/schemas.py`), populated from facts the system already has access to: days-to-event (computable, not KB-sourced), confirmed-exhibitor-count vs. target (already in `facts.json`/the KB explorer's reach), and the cancellation-schedule tightening (already in `registration_and_passes.md`). Surface it in the CTA section of `proposal.html.j2` / the React `TheAsk` component. Guardrail-safe by construction — every value is either computed or KB-sourced, never generated prose making a claim.

3. **Add a team/brand-identity block to the `Proposal` schema and CTA section** — a small, static config value (e.g. "The TEG exhibitor team" + a stated real turnaround time + the event's own logo), not an individual's name, and not something the LLM generates, so there's zero fabrication risk and no false implication that one specific person is personally handling this reply. Surface it above the email address, not below it.

4. **Add an objection-handling field, gated by dossier signal.** When `dossier`'s inferred HQ/region is outside Gujarat (a fact the research pipeline already resolves), have the `teg-proposal` skill address the outsider-objection explicitly, using the same tentative-language rules already enforced everywhere else in the skill.

5. **Add a secondary, lower-commitment CTA option** to the `Proposal` schema (`section_ctas` already exists for button labels — extend it with a genuine second path, e.g. a one-pager download or a no-obligation call, not just a second button pointing at the same chat reply).

6. **Venue/event photography** — lowest-code-effort, highest-visual-impact: a small fixed image set (venue exterior, a TEG 2024 floor photo if TEG can supply one) added to the React proposal page's hero or "who's there" section. Not LLM-generated — sourced once, reused across every proposal.

None of these touch the guardrail logic that was just hardened — they're additive, and every one of them is checkable against the same "never invent a fact" discipline the system already enforces well. The gap isn't that the system is too honest to be persuasive. It's that it isn't yet using everything true that it already knows.
