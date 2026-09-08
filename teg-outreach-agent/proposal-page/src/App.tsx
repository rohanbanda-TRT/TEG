import "./theme.css";
import type { Payload } from "./lib/types";
import { GROWTH, INDUSTRIES } from "./lib/chartData";
import { ProposalHeader } from "./sections/ProposalHeader";
import { Hero } from "./sections/Hero";
import { CurrentState } from "./sections/CurrentState";
import { GrowthOpportunity } from "./sections/GrowthOpportunity";
import { MarketOpportunity } from "./sections/MarketOpportunity";
import { TEGEnablement } from "./sections/TEGEnablement";
import { ThreeDayPlan } from "./sections/ThreeDayPlan";
import { PotentialOutcomes } from "./sections/PotentialOutcomes";
import { Recommendation } from "./sections/Recommendation";
import { Footer } from "./sections/Footer";

// The two frontend-owned static datasets — passed down as props rather than
// imported inside the leaf chart components, so those components stay
// data-agnostic and this is the one place that decides what "TEG's scale"
// and "the full industry list" mean.
const GROWTH_SERIES = [
  { label: "Attendees", from: GROWTH.attendees[0], to: GROWTH.attendees[1] },
  { label: "Exhibitors", from: GROWTH.exhibitors[0], to: GROWTH.exhibitors[1] },
];

/**
 * The page narrative, top to bottom: the opportunity (hero) -> where the
 * company is today -> the growth move available to it -> why this market ->
 * how TEG specifically helps -> the operating plan -> what it could lead to
 * -> the recommendation. Every section is presentation-only against the
 * same `Proposal` the backend already produces — nothing here changes what
 * gets generated, only how it's told.
 */
export function App({ payload }: { payload: Payload }) {
  const p = payload.proposal;
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;

  return (
    <>
      <ProposalHeader mailHref={mail} />
      <Hero p={p} version={payload.version} generatedOn={payload.generated_on} />
      <CurrentState p={p} />
      <GrowthOpportunity stages={p.growth_journey} company={p.company} />
      <MarketOpportunity p={p} allIndustries={INDUSTRIES} growthSeries={GROWTH_SERIES} />
      <TEGEnablement p={p} />
      <ThreeDayPlan p={p} />
      <PotentialOutcomes p={p} />
      <Recommendation p={p} />
      <Footer payload={payload} />
    </>
  );
}
