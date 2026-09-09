import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { Icon } from "../components/Icon";

/**
 * The operating plan — what the company would actually DO, not what
 * happens at the event. `how_a_teg_plays_out` is a flat, variable-length
 * list (3-6 items per the generation prompt) with no day-level metadata, so
 * this renders as a numbered horizontal flow (numbered circle -> arrow ->
 * next) rather than inventing a Before/Day 1/Day 2/Day 3/After structure
 * the data doesn't actually contain.
 */
export function ThreeDayPlan({ p }: { p: Proposal }) {
  if (!p.how_a_teg_plays_out.length) return null;
  return (
    <Section band="alt" id="plan" wide>
      <div className="sec-head">
        <span className="eyebrow">The operating plan</span>
        <h2>How {p.company} would work the three days</h2>
      </div>
      <ol className="plan-flow">
        {p.how_a_teg_plays_out.map((step, i) => (
          <Reveal key={i} as="li" className="plan-step" delay={i * 0.06}>
            <span className="plan-step__num" aria-hidden="true" />
            <p>{step}</p>
            <span className="plan-step__arrow" aria-hidden="true">
              <Icon name="arrow" size={18} />
            </span>
          </Reveal>
        ))}
      </ol>
    </Section>
  );
}
