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

export function Charts({ p }: { p: Proposal }) {
  return (
    <Section band="light" id="numbers">
      <Reveal>
        <h2>The numbers behind TEG</h2>
      </Reveal>

      {p.sector_fit.length > 0 && (
        <Reveal>
          <h3 style={{ marginTop: "2rem" }}>How your sector benefits</h3>
          <SectorFitBars rows={p.sector_fit} />
        </Reveal>
      )}

      <Reveal>
        <h3 style={{ marginTop: "2rem" }}>The track record</h3>
        <ul>
          {p.proof.map((x, i) => (
            <li key={i}>{x}</li>
          ))}
        </ul>
        <GrowthBars />
      </Reveal>

      <Reveal>
        <h3 style={{ marginTop: "2rem" }}>Who's in the room</h3>
        <IndustryMix />
      </Reveal>

      {p.peer_companies.length > 0 && (
        <Reveal>
          <div style={{ marginTop: "1.5rem" }}>
            <PeerStat names={p.peer_companies} />
          </div>
        </Reveal>
      )}

      <Reveal>
        <h3 style={{ marginTop: "2rem" }}>How it converts</h3>
        <Funnel steps={FUNNEL} />
      </Reveal>
    </Section>
  );
}
