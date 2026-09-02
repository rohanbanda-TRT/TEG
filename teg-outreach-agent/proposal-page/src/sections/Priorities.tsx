import type { Proposal } from "../lib/types";
import { sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

export function Priorities({ p }: { p: Proposal }) {
  if (!p.pains.length) return null;
  return (
    <Section band="alt" id="priorities">
      <Reveal>
        <h2>Where TEG moves the needle for you</h2>
      </Reveal>
      <div style={{ display: "grid", gap: "1rem", marginTop: "1.5rem" }}>
        {p.pains.map((pain, i) => (
          <Reveal key={i} delay={i * 0.08}>
            <div className="card">
              <strong>{pain.pain}</strong>
              <p style={{ margin: ".4rem 0 0" }}>{pain.teg_answer}</p>
            </div>
          </Reveal>
        ))}
      </div>
      <div style={{ marginTop: "1.5rem" }}>
        <a className="cta cta--ghost" href="#journey">
          {sectionCta(p, "priorities")}
        </a>
      </div>
    </Section>
  );
}
