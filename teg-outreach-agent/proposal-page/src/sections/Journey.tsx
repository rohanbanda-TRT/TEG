import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

export function Journey({ p }: { p: Proposal }) {
  if (!p.how_a_teg_plays_out.length) return null;
  return (
    <Section band="alt" id="journey">
      <Reveal>
        <h2>How your three days play out</h2>
      </Reveal>
      <ol style={{ listStyle: "none", padding: 0, marginTop: "1.5rem" }}>
        {p.how_a_teg_plays_out.map((step, i) => (
          <Reveal key={i} delay={i * 0.1}>
            <li
              style={{
                display: "flex",
                gap: "1rem",
                padding: ".75rem 0",
                borderLeft: "2px solid var(--teg-cyan)",
                paddingLeft: "1rem",
                marginLeft: ".5rem",
              }}
            >
              <b style={{ color: "var(--teg-cyan)" }}>{i + 1}</b>
              <span>{step}</span>
            </li>
          </Reveal>
        ))}
      </ol>
    </Section>
  );
}
