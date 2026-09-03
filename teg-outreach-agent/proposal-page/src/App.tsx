import "./theme.css";
import type { Payload } from "./lib/types";
import { Hero } from "./sections/Hero";
import { Priorities } from "./sections/Priorities";
import { SectorFit, TheRoom, Mechanism } from "./sections/Charts";
import { GrowthJourney } from "./sections/GrowthJourney";
import { Journey } from "./sections/Journey";
import { TheAsk } from "./sections/TheAsk";
import { Section } from "./components/Section";
import { Reveal } from "./components/Reveal";
import { TEG_LOGO_DATA_URI } from "./lib/brand";

function linkify(step: string) {
  const m = step.match(/https?:\/\/\S+|[\w.-]+\.com\/\S+/);
  if (!m) return step;
  const href = m[0].startsWith("http") ? m[0] : `https://${m[0]}`;
  return (
    <a href={href} target="_blank" rel="noopener">
      {step}
    </a>
  );
}

export function App({ payload }: { payload: Payload }) {
  const p = payload.proposal;
  return (
    <>
      <Hero p={p} version={payload.version} generatedOn={payload.generated_on} />

      {p.executive_summary && (
        <Section band="light" id="summary">
          <Reveal>
            <div className="sec-head">
              <span className="eyebrow">In short</span>
            </div>
            <p style={{ fontSize: "1.25rem", lineHeight: 1.7, color: "var(--ink)" }}>
              {p.executive_summary}
            </p>
          </Reveal>
        </Section>
      )}

      <GrowthJourney stages={p.growth_journey} company={p.company} />
      <Priorities p={p} />
      <SectorFit p={p} />
      <TheRoom p={p} />
      <Mechanism />
      <Journey p={p} />
      <TheAsk p={p} />

      <footer className="footer section--dark">
        <div className="container">
          <img src={TEG_LOGO_DATA_URI} alt="Tech Expo Gujarat" className="footer__logo" />
          <p className="footer__tagline">Beacon of Rising Innovation &amp; AI</p>
          <p style={{ fontWeight: 600, marginTop: "1.25rem" }}>Contact: {p.contact}</p>
          <ul>
            {p.next_steps.map((s, i) => (
              <li key={i}>{linkify(s)}</li>
            ))}
          </ul>
          <small>
            v{payload.version} · {payload.generated_on} · This is an information document, not a
            contract.{" "}
            <a href={payload.pdf_url} target="_blank" rel="noopener">
              Download as PDF
            </a>
          </small>
          <small>© AIMED TECH EXPO GUJARAT LLP</small>
        </div>
      </footer>
    </>
  );
}
