import { TEG_LOGO_DATA_URI } from "../lib/brand";
import { ScrollProgress } from "../components/ScrollProgress";

const LINKS: [string, string][] = [
  ["#today", "Today"],
  ["#opportunity", "Opportunity"],
  ["#market", "Market"],
  ["#plan", "Plan"],
  ["#recommendation", "Next step"],
];

/** A real in-page nav, not just an identity strip — orientation for a long
 * document, with section links so the reader can jump around it like any
 * other page rather than only scrolling linearly. */
export function ProposalHeader({ mailHref }: { mailHref: string }) {
  return (
    <header className="pnav">
      <div className="pnav__brand">
        <img src={TEG_LOGO_DATA_URI} alt="Tech Expo Gujarat" className="pnav__logo" />
        <span className="pnav__wordmark">TEG 2026</span>
      </div>
      <nav className="pnav__links" aria-label="Proposal sections">
        {LINKS.map(([href, label]) => (
          <a key={href} href={href}>
            {label}
          </a>
        ))}
      </nav>
      <a className="cta pnav__cta" href={mailHref}>
        Talk to the team
      </a>
      <ScrollProgress variant="header" />
    </header>
  );
}
