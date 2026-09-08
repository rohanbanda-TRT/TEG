import { useRef } from "react";
import { motion, useScroll, useReducedMotion } from "framer-motion";
import type { JourneyStage } from "../lib/types";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";

/**
 * The growth argument, told as one connected flow: where the company is now,
 * the move that's available to it, what's stood in the way of it so far, how
 * TEG opens market access, how they'd actually engage, and where it could
 * lead. Six stages, always in this order — `_clamp_growth_journey` on the
 * backend guarantees all six or none, so there's no partial-journey case to
 * design for here.
 *
 * The connector line draws itself in as the reader scrolls through the
 * argument (not on mount) — its fill tracks how far down the story they've
 * actually read.
 */

const STAGE_LABEL: Record<string, string> = {
  today: "Current position",
  growth_move: "The growth move",
  barrier: "What's stood in the way",
  teg_opportunity: "How TEG opens market access",
  action: "How you'd engage",
  potential: "Where the opportunity leads",
};

const STAGE_KIND: Record<string, string> = {
  today: "gj-stage--now",
  growth_move: "gj-stage--move",
  barrier: "gj-stage--barrier",
  teg_opportunity: "gj-stage--teg",
  action: "gj-stage--action",
  potential: "gj-stage--potential",
};

export function GrowthOpportunity({
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
    <Section band="alt" id="opportunity" wide>
      <div className="sec-head">
        <span className="eyebrow">The growth opportunity</span>
        <h2>How {company} could grow through TEG</h2>
        <p>
          Not a pitch for the event — a read on where you are, the move
          that's open to you, and the part three days on the floor could
          play in reaching it.
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
                  <span className="gj-stage__label">{STAGE_LABEL[s.stage] ?? s.stage}</span>
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
