import { useRef } from "react";
import { motion, useScroll, useReducedMotion } from "framer-motion";
import type { JourneyStage } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

/**
 * The six-stage growth argument — where the company is, where it could go,
 * what stops it, what TEG opens, how they'd work it, where it could lead.
 * Rendered as a connected vertical flow: each stage is a card, with a single
 * connector line down the left that draws itself in as the reader scrolls
 * through the list (not on mount) — the line's fill tracks how far down the
 * argument they've actually read.
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
  const wrapRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: wrapRef,
    offset: ["start 0.8", "end 0.55"],
    layoutEffect: false,
  });

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

      <div className="gj-wrap" ref={wrapRef}>
        <div className="gj-line" aria-hidden="true">
          <motion.div
            className="gj-line__fill"
            style={reduceMotion ? { transform: "scaleY(1)" } : { scaleY: scrollYProgress }}
          />
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
      </div>
    </Section>
  );
}
