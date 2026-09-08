import type { Proposal } from "../lib/types";
import { sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

export function Priorities({ p }: { p: Proposal }) {
  if (!p.pains.length) return null;
  return (
    <Section band="alt" id="priorities" wide>
      <div className="sec-head">
        <span className="eyebrow">Your priorities</span>
        <h2>Where TEG moves the needle for you</h2>
      </div>
      <div className="priorities-grid">
        {p.pains.map((pain, i) => (
          <Reveal key={i} delay={i * 0.08}>
            <div className="priority">
              <strong>{pain.pain}</strong>
              <p>{pain.teg_answer}</p>
            </div>
          </Reveal>
        ))}
      </div>
      <div style={{ textAlign: "center", marginTop: "2.5rem" }}>
        <a className="cta cta--ghost" href="#numbers">
          {sectionCta(p, "priorities")}
        </a>
      </div>
    </Section>
  );
}
