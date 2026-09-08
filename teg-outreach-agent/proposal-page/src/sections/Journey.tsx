import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

export function Journey({ p }: { p: Proposal }) {
  if (!p.how_a_teg_plays_out.length) return null;
  return (
    <Section band="alt" id="journey">
      <div className="sec-head">
        <span className="eyebrow">The plan</span>
        <h2>How your three days play out</h2>
      </div>
      <ol className="journey">
        {p.how_a_teg_plays_out.map((step, i) => (
          <li key={i}>
            <Reveal delay={i * 0.06}>
              <span>{step}</span>
            </Reveal>
          </li>
        ))}
      </ol>
    </Section>
  );
}
