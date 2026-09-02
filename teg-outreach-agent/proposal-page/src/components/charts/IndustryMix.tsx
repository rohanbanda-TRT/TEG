import { motion } from "framer-motion";
import { INDUSTRIES } from "../../lib/chartData";
import { useReveal } from "../../hooks/useReveal";

export function IndustryMix() {
  const { ref, shown } = useReveal();
  return (
    <div ref={ref}>
      <p className="chart-caption">
        Buyers attend across every sector — illustrative, not to scale
      </p>
      <div className="chart-rows" role="img" aria-label="Industries represented at TEG">
        {INDUSTRIES.map((name, i) => {
          const frac = 0.5 + (0.45 * i) / (INDUSTRIES.length - 1);
          return (
            <div className="chart-row" key={name}>
              <span className="chart-row__label">{name}</span>
              <span className="chart-row__track">
                <motion.span
                  className="chart-row__fill chart-row__fill--cyan"
                  initial={{ width: 0 }}
                  animate={shown ? { width: `${frac * 100}%` } : {}}
                  transition={{ duration: 0.5, delay: i * 0.03 }}
                />
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
