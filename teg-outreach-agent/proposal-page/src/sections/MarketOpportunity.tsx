import type { ReactNode } from "react";
import type { Proposal } from "../lib/types";
import type { GrowthSeries } from "../components/charts/GrowthBars";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { ChartCard } from "../components/ChartCard";
import { SectorFitBars } from "../components/charts/SectorFitBars";
import { PeerStat } from "../components/charts/PeerStat";
import { IndustryList } from "../components/charts/IndustryList";
import { GrowthBars } from "../components/charts/GrowthBars";

/**
 * "Why this market" — the company's sector and capabilities, connected to
 * the buyers actually in the room. Event-scale facts (attendee/exhibitor
 * growth) are real but not the point, so they're demoted into one muted,
 * dashed-border card at the end rather than given their own section.
 *
 * Returns null when there's nothing company-specific to show — a page full
 * of generic TEG facts with no connection to this company isn't "why this
 * market," it's an ad, which is exactly what this section exists to avoid.
 */
export function MarketOpportunity({
  p,
  allIndustries,
  growthSeries,
}: {
  p: Proposal;
  allIndustries: string[];
  growthSeries: GrowthSeries[];
}) {
  const hasIndustries = (p.target_industries?.length ?? 0) > 0;
  const hasPeers = p.peer_companies.length > 0;
  const hasFit = p.sector_fit.length > 0;
  if (!hasIndustries && !hasPeers && !hasFit) return null;

  // Cards vary a lot in height depending on how much a given proposal has to
  // say (a 5-lever sector-fit chart vs. a 4-chip industry list) — a locked
  // two-column CSS grid ties row heights together across both columns, so
  // a short card ends up stretched with dead space to match a tall neighbor
  // in the same row. Two independent flex columns avoid that: each one
  // reflows to its own content, nothing stretches to match anything else.
  const cards: ReactNode[] = [];

  if (hasIndustries) {
    cards.push(
      <Reveal key="industries">
        <ChartCard title="The buyers you'd actually meet" icon="pin">
          <IndustryList
            all={allIndustries}
            highlight={p.target_industries}
            note={p.target_industries_note}
          />
        </ChartCard>
      </Reveal>,
    );
  }
  if (hasFit) {
    cards.push(
      <Reveal key="fit">
        <ChartCard
          title="Where TEG's levers matter most"
          caption={`For a company like ${p.company}.`}
          icon="target"
        >
          <SectorFitBars rows={p.sector_fit} />
        </ChartCard>
      </Reveal>,
    );
  }
  if (hasPeers) {
    cards.push(
      <Reveal key="peers">
        <ChartCard title="Companies already testing this market" icon="users">
          <PeerStat
            names={p.peer_companies}
            sector={p.sector}
            sectorTotal={p.peers_in_sector_total}
            contextLine={p.peer_context_line}
          />
        </ChartCard>
      </Reveal>,
    );
  }
  if (growthSeries.length > 0) {
    cards.push(
      <Reveal key="scale">
        <ChartCard
          title="For context — TEG's own scale"
          caption={
            p.scale_note ||
            "The event itself is growing year over year; the numbers below are TEG's, not a forecast for your business."
          }
          icon="chart"
          muted
        >
          <GrowthBars series={growthSeries} />
        </ChartCard>
      </Reveal>,
    );
  }

  const left = cards.filter((_, i) => i % 2 === 0);
  const right = cards.filter((_, i) => i % 2 === 1);

  return (
    <Section band="light" id="market" wide>
      <div className="sec-head">
        <span className="eyebrow">Why this market</span>
        <h2>
          A market with the right signals for {p.company}
          {p.sector ? ` in ${p.sector}` : ""}
        </h2>
        {p.target_industries_note && <p>{p.target_industries_note}</p>}
      </div>

      <div className="market-grid">
        <div className="market-grid__col">{left}</div>
        {right.length > 0 && <div className="market-grid__col">{right}</div>}
      </div>
    </Section>
  );
}
