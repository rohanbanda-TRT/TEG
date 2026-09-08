import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { Icon } from "../components/Icon";

// cycled across however many proof points come back — no fixed count assumed
const ICONS: Array<Parameters<typeof Icon>[0]["name"]> = ["chart", "handshake", "route", "layers"];

/**
 * "What could these three days lead to" — roi_framing as the lead statement
 * (already written in tentative language by the generation prompt/
 * guardrails; this component doesn't add or soften hedging, it just
 * renders what the backend already produced), proof as short icon-card
 * evidence rather than a bulleted wall of text.
 */
export function PotentialOutcomes({ p }: { p: Proposal }) {
  const hasRoi = Boolean(p.roi_framing?.trim());
  const hasProof = p.proof.length > 0;
  if (!hasRoi && !hasProof) return null;

  return (
    <Section band="light" id="outcomes">
      <div className="sec-head sec-head--left">
        <span className="eyebrow">Potential outcomes</span>
        <h2>What these three days could lead to</h2>
      </div>

      {hasRoi && (
        <Reveal>
          <p className="outcomes-lead">{p.roi_framing}</p>
        </Reveal>
      )}

      {hasProof && (
        <div className="outcomes-grid">
          {p.proof.map((x, i) => (
            <Reveal key={i} delay={i * 0.06}>
              <div className="outcome-card">
                <span className="ibadge" aria-hidden="true">
                  <Icon name={ICONS[i % ICONS.length]} />
                </span>
                <p>{x}</p>
              </div>
            </Reveal>
          ))}
        </div>
      )}
    </Section>
  );
}
