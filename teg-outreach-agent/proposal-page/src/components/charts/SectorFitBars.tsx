import { motion } from "framer-motion";
import type { SectorFitRow } from "../../lib/types";
import { useReveal } from "../../hooks/useReveal";

/** HTML layout + an animated bar div — SVG text does not scale legibly. */
export function SectorFitBars({ rows }: { rows: SectorFitRow[] }) {
  const { ref, shown } = useReveal();
  return (
    <div ref={ref} className="chart-rows" role="img" aria-label="How TEG's levers weigh for your sector">
      {rows.map((r, i) => {
        const w = Math.max(1, Math.min(5, r.weight));
        return (
          <div className="chart-row" key={r.lever}>
            <span className="chart-row__label">{r.lever}</span>
            <span className="chart-row__track">
              <motion.span
                className="chart-row__fill"
                initial={{ width: 0 }}
                animate={shown ? { width: `${(w / 5) * 100}%` } : {}}
                transition={{ duration: 0.6, delay: i * 0.08 }}
              />
            </span>
            <span className="chart-row__value">{w}/5</span>
          </div>
        );
      })}
    </div>
  );
}
