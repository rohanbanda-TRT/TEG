import type { Proposal } from "../lib/types";
import { sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { CtaButton } from "../components/CtaButton";
import { Icon } from "../components/Icon";

/**
 * The core business logic of the whole page: each business challenge,
 * connected directly to the specific TEG mechanism that addresses it. Same
 * underlying `pains` data as "Where you are today," but presented
 * differently there (as a fact about the company) than here (as a causal
 * pair — challenge, then how TEG answers it) — deliberately not the same
 * rendered copy twice.
 *
 * Rendered as two independent columns rather than a locked grid: a
 * challenge/answer pair with a longer sentence on one side shouldn't force
 * its row-neighbor to stretch and sit on a pile of dead space — each card
 * should only ever be as tall as its own text.
 */
export function TEGEnablement({ p }: { p: Proposal }) {
  if (!p.pains.length) return null;

  const cards = p.pains.map((pain, i) => (
    <Reveal key={i} delay={i * 0.07}>
      <div className="enable-card">
        <div className="enable-card__row enable-card__row--challenge">
          <span className="ibadge ibadge--sm ibadge--navy" aria-hidden="true">
            <Icon name="target" size={16} />
          </span>
          <div>
            <span className="enable-card__kicker">Business challenge</span>
            <p className="enable-card__text">{pain.pain}</p>
          </div>
        </div>
        <div className="enable-card__connector" aria-hidden="true" />
        <div className="enable-card__row enable-card__row--answer">
          <span className="ibadge ibadge--sm" aria-hidden="true">
            <Icon name="spark" size={16} />
          </span>
          <div>
            <span className="enable-card__kicker">TEG enablement</span>
            <p className="enable-card__text">{pain.teg_answer}</p>
          </div>
        </div>
      </div>
    </Reveal>
  ));
  const left = cards.filter((_, i) => i % 2 === 0);
  const right = cards.filter((_, i) => i % 2 === 1);

  return (
    <Section band="light" id="how-teg-helps">
      <div className="sec-head">
        <span className="eyebrow">How TEG can help</span>
        <h2>What specifically makes this easier for {p.company}</h2>
      </div>
      <div className="enable-grid">
        <div className="enable-grid__col">{left}</div>
        {right.length > 0 && <div className="enable-grid__col">{right}</div>}
      </div>
      <div style={{ textAlign: "center", marginTop: "2.5rem" }}>
        <CtaButton href="#plan" variant="ghost">
          {sectionCta(p, "priorities")}
        </CtaButton>
      </div>
    </Section>
  );
}
