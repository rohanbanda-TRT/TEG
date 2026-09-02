import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { GrowthBars } from "../components/charts/GrowthBars";
import { IndustryMix } from "../components/charts/IndustryMix";
import { SectorFitBars } from "../components/charts/SectorFitBars";
import { Funnel } from "../components/charts/Funnel";
import { PeerStat } from "../components/charts/PeerStat";

const FUNNEL: [string, string][] = [
  ["15,000+ visitors", "cross-industry decision-makers"],
  ["Pre-scheduled 1:1 meetings", "matched to your sectors"],
  ["Qualified conversations", "live demos, real intent"],
  ["Partnerships & pipeline", "the follow-up that starts here"],
];

export function SectorFit({ p }: { p: Proposal }) {
  if (!p.sector_fit.length) return null;
  return (
    <Section band="light" id="numbers">
      <div className="sec-head">
        <span className="eyebrow">Fit for {p.sector ?? "your sector"}</span>
        <h2>How your sector benefits</h2>
        <p>Which of TEG's levers matter most for a company like {p.company}.</p>
      </div>
      <Reveal>
        <div className="chart-block">
          <SectorFitBars rows={p.sector_fit} />
        </div>
      </Reveal>
    </Section>
  );
}

export function TheRoom({ p }: { p: Proposal }) {
  return (
    <Section band="alt" id="room">
      <div className="sec-head">
        <span className="eyebrow">The audience</span>
        <h2>Who's in the room</h2>
        <p>A growing, cross-industry crowd of buyers — and companies like yours already committed.</p>
      </div>

      {p.proof.length > 0 && (
        <Reveal>
          <div className="chart-block">
            <h3>The track record</h3>
            <ul style={{ color: "var(--slate)", paddingLeft: "1.2rem", margin: "0.75rem 0 1.5rem" }}>
              {p.proof.map((x, i) => (
                <li key={i} style={{ margin: "0.4rem 0" }}>
                  {x}
                </li>
              ))}
            </ul>
            <GrowthBars />
          </div>
        </Reveal>
      )}

      <Reveal>
        <div className="chart-block">
          <h3>Every industry, under one roof</h3>
          <IndustryMix />
        </div>
      </Reveal>

      {p.peer_companies.length > 0 && (
        <Reveal>
          <div className="chart-block">
            <h3>Peers already confirmed</h3>
            <div style={{ marginTop: "1rem" }}>
              <PeerStat names={p.peer_companies} />
            </div>
          </div>
        </Reveal>
      )}
    </Section>
  );
}

export function Mechanism() {
  return (
    <Section band="light" id="mechanism">
      <div className="sec-head">
        <span className="eyebrow">How it works</span>
        <h2>From footfall to pipeline</h2>
        <p>Illustrative of the TEG mechanism — pre-scheduled meetings do the heavy lifting.</p>
      </div>
      <Reveal>
        <div className="chart-block">
          <Funnel steps={FUNNEL} />
        </div>
      </Reveal>
    </Section>
  );
}
