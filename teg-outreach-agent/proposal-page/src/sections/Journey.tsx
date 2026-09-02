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
      <ol
        style={{
          listStyle: "none",
          padding: 0,
          margin: "2rem 0 0",
          borderLeft: "2px solid var(--teg-line)",
          marginLeft: "1.15rem",
        }}
      >
        {p.how_a_teg_plays_out.map((step, i) => (
          <Reveal key={i} delay={i * 0.1}>
            <li
              style={{
                position: "relative",
                display: "flex",
                gap: "1rem",
                alignItems: "baseline",
                padding: "0 0 1.75rem 1.75rem",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  left: "-1.15rem",
                  transform: "translateX(-50%)",
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  background: "var(--teg-cyan)",
                  color: "#fff",
                  fontWeight: 800,
                  fontSize: ".9rem",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {i + 1}
              </span>
              <span style={{ fontSize: "1.05rem" }}>{step}</span>
            </li>
          </Reveal>
        ))}
      </ol>
    </Section>
  );
}
