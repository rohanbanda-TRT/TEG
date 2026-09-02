import { motion } from "framer-motion";
import { GROWTH } from "../../lib/chartData";
import { useCountUp } from "../../hooks/useCountUp";
import { useReveal } from "../../hooks/useReveal";

function Bar({ label, a, b, max, shown }: { label: string; a: number; b: number; max: number; shown: boolean }) {
  const n24 = useCountUp(a, shown);
  const n26 = useCountUp(b, shown);
  return (
    <div className="growth-group">
      <div className="growth-group__bars">
        <div className="growth-bar">
          <span className="growth-bar__value">{n24.toLocaleString()}</span>
          <motion.div
            className="growth-bar__fill growth-bar__fill--muted"
            initial={{ height: 0 }}
            animate={shown ? { height: `${(a / max) * 100}%` } : {}}
            transition={{ duration: 0.7 }}
          />
        </div>
        <div className="growth-bar">
          <span className="growth-bar__value">{n26.toLocaleString()}</span>
          <motion.div
            className="growth-bar__fill"
            initial={{ height: 0 }}
            animate={shown ? { height: `${(b / max) * 100}%` } : {}}
            transition={{ duration: 0.7, delay: 0.1 }}
          />
        </div>
      </div>
      <div className="growth-group__label">{label}</div>
    </div>
  );
}

export function GrowthBars() {
  const { ref, shown } = useReveal();
  const max = Math.max(GROWTH.attendees[1], GROWTH.exhibitors[1]);
  return (
    <div ref={ref} role="img" aria-label="TEG 2024 to 2026 growth">
      <div className="growth-chart">
        <Bar label="Attendees" a={GROWTH.attendees[0]} b={GROWTH.attendees[1]} max={max} shown={shown} />
        <Bar label="Exhibitors" a={GROWTH.exhibitors[0]} b={GROWTH.exhibitors[1]} max={max} shown={shown} />
      </div>
      <div className="growth-legend">
        <span><i className="growth-legend__dot growth-legend__dot--muted" /> TEG 2024 (actual)</span>
        <span><i className="growth-legend__dot" /> TEG 2026 (target)</span>
      </div>
    </div>
  );
}
