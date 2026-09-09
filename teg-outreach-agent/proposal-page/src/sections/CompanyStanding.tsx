import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { Icon } from "../components/Icon";

/**
 * Deep-research-informed standing + TEG fit — only rendered once a
 * background deep-research pass has landed for this company
 * (Proposal.company_standing / teg_fit_points are both empty until then;
 * see docs/superpowers/specs/2026-09-09-background-deep-research-design.md).
 * Deliberately separate from CurrentState: that section reflects what the
 * CONVERSATION established (executive_summary, pains); this reflects what
 * independent research found, and what it specifically suggests about TEG.
 */
export function CompanyStanding({ p }: { p: Proposal }) {
  const standing = p.company_standing?.trim();
  const fitPoints = p.teg_fit_points ?? [];
  if (!standing && fitPoints.length === 0) return null;

  return (
    <Section band="alt" id="standing">
      <div className="sec-head sec-head--left">
        <span className="eyebrow">Independent research on {p.company}</span>
      </div>

      <div className="state-grid">
        {standing && (
          <Reveal direction="right">
            <div className="state-card">
              <span className="ibadge" aria-hidden="true">
                <Icon name="layers" />
              </span>
              <p className="standing-copy">{standing}</p>
            </div>
          </Reveal>
        )}

        {fitPoints.length > 0 && (
          <div className="reality">
            {fitPoints.map((point, i) => (
              <Reveal key={i} delay={i * 0.07}>
                <div className="reality__item">
                  <span className="ibadge ibadge--sm" aria-hidden="true">
                    <Icon name="target" size={16} />
                  </span>
                  <div className="reality__body">
                    <strong>{point}</strong>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        )}
      </div>
    </Section>
  );
}
