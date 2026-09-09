import { motion } from "framer-motion";

const fillVariants = {
  hidden: { scaleY: 0 },
  show: { scaleY: 1 },
};

function Group({ label, a, b }: { label: string; a: number; b: number }) {
  // Each group scales to its own 2026 target so both read as "roughly 2x"
  // regardless of the raw magnitude gap between attendees and exhibitors.
  const max = Math.max(a, b, 1);
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

export interface GrowthSeries {
  label: string;
  from: number;
  to: number;
}

/**
 * A compact before/after bar comparison. Takes its series as a prop — no
 * hardcoded TEG numbers baked in here; the caller (a page-level constant
 * today, potentially a Proposal field tomorrow) owns the data.
 */
export function GrowthBars({
  series,
  fromLabel = "2024 (actual)",
  toLabel = "2026 (target)",
}: {
  series: GrowthSeries[];
  fromLabel?: string;
  toLabel?: string;
}) {
  if (!series.length) return null;
  return (
    <div role="img" aria-label="Event scale, before and after">
      <div className="growth-chart">
        {series.map((s) => (
          <Group key={s.label} label={s.label} a={s.from} b={s.to} />
        ))}
      </div>
      <div className="growth-legend">
        <span>
          <i className="growth-legend__dot growth-legend__dot--muted" /> {fromLabel}
        </span>
        <span>
          <i className="growth-legend__dot" /> {toLabel}
        </span>
      </div>
    </div>
  );
}
