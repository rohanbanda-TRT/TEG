import { motion } from "framer-motion";
import type { SectorFitRow } from "../../lib/types";

const fillVariants = {
  hidden: { scaleX: 0 },
  show: { scaleX: 1 },
};

export function SectorFitBars({ rows }: { rows: SectorFitRow[] }) {
  return (
    <div className="chart-rows" role="img" aria-label="How TEG's levers weigh for your sector">
      {rows.map((r, i) => {
        const w = Math.max(1, Math.min(5, r.weight));
        return (
          <div className="chart-row" key={r.lever}>
            <span className="chart-row__label">{r.lever}</span>
            {/* whileInView triggers here, on the track — a fixed-size element.
                Triggering it on the fill itself doesn't work: the fill starts
                at scaleX:0 (zero width), so it can never satisfy its own
                "80% visible" viewport threshold. */}
            <motion.span
              className="chart-row__track"
              initial="hidden"
              whileInView="show"
              viewport={{ once: true, amount: 0.8 }}
              transition={{ type: "spring", stiffness: 110, damping: 18, delay: i * 0.05 }}
            >
              <motion.span
                className="chart-row__fill"
                variants={fillVariants}
                style={{ width: `${(w / 5) * 100}%` }}
              />
            </motion.span>
            <span className="chart-row__value">{w}/5</span>
          </div>
        );
      })}
    </div>
  );
}
