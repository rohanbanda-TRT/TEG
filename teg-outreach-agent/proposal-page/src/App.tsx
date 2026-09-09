import "./theme.css";
import type { Payload } from "./lib/types";
import { GROWTH, INDUSTRIES } from "./lib/chartData";
import { ProposalHeader } from "./sections/ProposalHeader";
import { Hero } from "./sections/Hero";
import { CurrentState } from "./sections/CurrentState";
import { CompanyStanding } from "./sections/CompanyStanding";
import { GrowthOpportunity } from "./sections/GrowthOpportunity";
import { MarketOpportunity } from "./sections/MarketOpportunity";
import { TEGEnablement } from "./sections/TEGEnablement";
import { ThreeDayPlan } from "./sections/ThreeDayPlan";
import { PotentialOutcomes } from "./sections/PotentialOutcomes";
import { Recommendation } from "./sections/Recommendation";
import { Footer } from "./sections/Footer";
import { CustomHtmlSection } from "./components/CustomHtmlSection";

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
 * company is today (from the conversation) -> where they stand more deeply
 * (from independent research, when a background deep-research pass has
 * landed — CompanyStanding renders nothing otherwise) -> the growth move
 * available to it -> why this market -> how TEG specifically helps -> the
 * operating plan -> what it could lead to -> the recommendation. Every
 * section is presentation-only against the same `Proposal` the backend
 * already produces — nothing here changes what gets generated, only how
 * it's told.
 */
export function App({ payload }: { payload: Payload }) {
  const p = payload.proposal;
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;

  // Group custom HTML sections by position
  const customSections = p.custom_html_sections || [];
  const afterHero = customSections.filter(s => s.position === "after_hero");
  const beforePains = customSections.filter(s => s.position === "before_pains");
  const afterProof = customSections.filter(s => s.position === "after_proof");
  const beforeClosing = customSections.filter(s => s.position === "before_closing");

  return (
    <>
      <ProposalHeader mailHref={mail} />
      <Hero p={p} version={payload.version} generatedOn={payload.generated_on} />
      {afterHero.map(section => (
        <CustomHtmlSection
          key={section.section_id}
          title={section.title}
          htmlContent={section.html_content}
          confidence={section.confidence}
        />
      ))}
      <CurrentState p={p} />
      <CompanyStanding p={p} />
      {beforePains.map(section => (
        <CustomHtmlSection
          key={section.section_id}
          title={section.title}
          htmlContent={section.html_content}
          confidence={section.confidence}
        />
      ))}
      <GrowthOpportunity stages={p.growth_journey} company={p.company} />
      <MarketOpportunity p={p} allIndustries={INDUSTRIES} growthSeries={GROWTH_SERIES} />
      <TEGEnablement p={p} />
      <ThreeDayPlan p={p} />
      {afterProof.map(section => (
        <CustomHtmlSection
          key={section.section_id}
          title={section.title}
          htmlContent={section.html_content}
          confidence={section.confidence}
        />
      ))}
      <PotentialOutcomes p={p} />
      {beforeClosing.map(section => (
        <CustomHtmlSection
          key={section.section_id}
          title={section.title}
          htmlContent={section.html_content}
          confidence={section.confidence}
        />
      ))}
      <Recommendation p={p} />
      <Footer payload={payload} />
    </>
  );
}
