import type { JourneyStage } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

/**
 * The six-stage growth argument — where the company is, where it could go,
 * what stops it, what TEG opens, how they'd work it, where it could lead.
 * Rendered as a connected vertical flow: each stage is a card, arrows between.
 */

const STAGE_LABEL: Record<string, string> = {
  today: "Today",
  growth_move: "The growth move",
  barrier: "What stands in the way",
  teg_opportunity: "What Tech Expo Gujarat opens",
  action: "How you'd work the three days",
  potential: "Where it could lead",
};

const STAGE_KIND: Record<string, string> = {
  today: "gj-stage--now",
  growth_move: "gj-stage--move",
  barrier: "gj-stage--barrier",
  teg_opportunity: "gj-stage--teg",
  action: "gj-stage--action",
  potential: "gj-stage--potential",
};

export function GrowthJourney({
  stages,
  company,
}: {
  stages?: JourneyStage[];
  company: string;
}) {
  if (!stages || stages.length === 0) return null;

  return (
    <Section band="light" id="growth">
      <div className="sec-head">
        <span className="eyebrow">The opportunity</span>
        <h2>How {company} could grow through TEG</h2>
        <p>
          Not a pitch for the event — a read on where you are, what's next, and
          the part three days on the floor could play in getting there.
        </p>
      </div>

      <ol className="gj">
        {stages.map((s, i) => (
          <li key={i} className={`gj-stage ${STAGE_KIND[s.stage] ?? ""}`}>
            <Reveal delay={i * 0.05}>
              <div className="gj-stage__inner">
                <span className="gj-stage__label">
                  {STAGE_LABEL[s.stage] ?? s.stage}
                </span>
                <h3 className="gj-stage__title">{s.title}</h3>
                {s.points.length > 0 && (
                  <ul className="gj-stage__points">
                    {s.points.map((pt, j) => (
                      <li key={j}>{pt}</li>
                    ))}
                  </ul>
                )}
              </div>
            </Reveal>
          </li>
        ))}
      </ol>
    </Section>
  );
}
