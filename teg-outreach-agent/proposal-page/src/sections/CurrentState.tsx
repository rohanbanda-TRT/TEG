import type { Proposal } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { Icon } from "../components/Icon";

/**
 * "Where you are today" — the executive summary as a large statement, and
 * the pains as an icon-badged reality list rather than a card grid. A plain
 * list has no "boxes that must line up": it stays legible whether there are
 * 2 pains or 6, and whether one runs to a full sentence longer than its
 * neighbor — nothing here depends on matching heights.
 */
export function CurrentState({ p }: { p: Proposal }) {
  const hasSummary = Boolean(p.executive_summary?.trim());
  const hasPains = p.pains.length > 0;
  if (!hasSummary && !hasPains) return null;

  return (
    <Section band="light" id="today">
      <div className="sec-head sec-head--left">
        <span className="eyebrow">Where {p.company} is today</span>
      </div>

      <div className="state-grid">
        {hasSummary && (
          <Reveal direction="right">
            <div className="state-card">
              <span className="ibadge" aria-hidden="true">
                <Icon name="compass" />
              </span>
              <p className="state-statement">{p.executive_summary}</p>
            </div>
          </Reveal>
        )}

        {hasPains && (
          <div className="reality">
            {p.pains.map((pain, i) => (
              <Reveal key={i} delay={i * 0.07}>
                <div className="reality__item">
                  <span className="ibadge ibadge--sm" aria-hidden="true">
                    <Icon name="compass" size={16} />
                  </span>
                  <div className="reality__body">
                    <strong>{pain.pain}</strong>
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
