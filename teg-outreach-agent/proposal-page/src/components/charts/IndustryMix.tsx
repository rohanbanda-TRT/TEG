import { motion } from "framer-motion";
import { INDUSTRIES } from "../../lib/chartData";

/**
 * The 18 buyer industries TEG draws, with the ones this prospect actually
 * sells to pulled out and highlighted. Deliberately NOT a bar chart: we have
 * no per-industry attendance split, and inventing bar lengths to look like
 * data would be a fabricated statistic.
 */
export function IndustryMix({
  highlight = [],
  note,
}: {
  highlight?: string[];
  note?: string;
}) {
  const hl = new Set(highlight.map((h) => h.toLowerCase()));
  const rest = INDUSTRIES.filter((n) => !hl.has(n.toLowerCase()));

  return (
    <div>
      {highlight.length > 0 ? (
        <>
          <p className="chart-caption">
            {note || "The industries TEG draws that matter most for you."}
          </p>
          <div className="ind-grid ind-grid--hl">
            {highlight.map((name, i) => (
              <motion.span
                className="ind-chip ind-chip--on"
                key={name}
                initial={{ opacity: 0, scale: 0.85 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, amount: 0.8 }}
                transition={{ type: "spring", stiffness: 220, damping: 16, delay: i * 0.05 }}
              >
                {name}
              </motion.span>
            ))}
          </div>
          <p className="ind-rest-label">Plus buyers from every other TEG industry:</p>
        </>
      ) : (
        <p className="chart-caption">
          TEG 2026 draws buyers across all {INDUSTRIES.length} of these industries.
        </p>
      )}
      <div className="ind-grid">
        {rest.map((name) => (
          <span className="ind-chip" key={name}>
            {name}
          </span>
        ))}
      </div>
    </div>
  );
}
