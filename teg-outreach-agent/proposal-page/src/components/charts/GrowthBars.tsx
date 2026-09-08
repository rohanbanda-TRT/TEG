import { motion } from "framer-motion";
import { GROWTH } from "../../lib/chartData";

const fillVariants = {
  hidden: { scaleY: 0 },
  show: { scaleY: 1 },
};

function Group({ label, a, b }: { label: string; a: number; b: number }) {
  // Each group scales to its own 2026 target so both read as "~2x growth"
  // regardless of the raw magnitude gap between attendees and exhibitors.
  const max = Math.max(a, b);
  return (
    <div className="growth-group">
      <div className="growth-group__bars">
        {/* whileInView triggers on the fixed-height track, not the fill —
            the fill starts at scaleY:0 (zero height), so it can never
            satisfy its own "visible" viewport threshold on its own. */}
        <motion.div
          className="growth-bar"
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.6 }}
          transition={{ type: "spring", stiffness: 90, damping: 16 }}
        >
          <span className="growth-bar__value">{a.toLocaleString()}</span>
          <motion.span
            className="growth-bar__fill growth-bar__fill--muted"
            variants={fillVariants}
            style={{ height: `${(a / max) * 100}%` }}
          />
        </motion.div>
        <motion.div
          className="growth-bar"
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.6 }}
          transition={{ type: "spring", stiffness: 90, damping: 16, delay: 0.08 }}
        >
          <span className="growth-bar__value">{b.toLocaleString()}</span>
          <motion.span
            className="growth-bar__fill"
            variants={fillVariants}
            style={{ height: `${(b / max) * 100}%` }}
          />
        </motion.div>
      </div>
      <div className="growth-group__label">{label}</div>
    </div>
  );
}

export function GrowthBars() {
  return (
    <div role="img" aria-label="TEG 2024 to 2026 growth">
      <div className="growth-chart">
        <Group label="Attendees" a={GROWTH.attendees[0]} b={GROWTH.attendees[1]} />
        <Group label="Exhibitors" a={GROWTH.exhibitors[0]} b={GROWTH.exhibitors[1]} />
      </div>
      <div className="growth-legend">
        <span>
          <i className="growth-legend__dot growth-legend__dot--muted" /> TEG 2024 (actual)
        </span>
        <span>
          <i className="growth-legend__dot" /> TEG 2026 (target)
        </span>
      </div>
    </div>
  );
}
