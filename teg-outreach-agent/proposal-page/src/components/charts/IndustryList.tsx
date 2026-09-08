import { motion } from "framer-motion";

/**
 * The industries TEG draws buyers from, with the ones this prospect actually
 * sells to pulled out and highlighted. `all` is passed in rather than
 * imported — the caller owns the master list, this component just renders
 * whatever it's given. Deliberately NOT a bar chart: there's no per-industry
 * attendance split, and inventing bar lengths to look like data would be a
 * fabricated statistic.
 *
 * The full static list is visually subordinate — company-relevant industries
 * lead, the complete roster is tucked behind a disclosure rather than
 * competing for attention.
 */
export function IndustryList({
  all,
  highlight = [],
  note,
}: {
  all: string[];
  highlight?: string[];
  note?: string;
}) {
  const hl = new Set(highlight.map((h) => h.toLowerCase()));
  const rest = all.filter((n) => !hl.has(n.toLowerCase()));

  if (highlight.length === 0) {
    return (
      <div>
        <p className="chart-card__cap">
          {note || `TEG 2026 draws buyers across all ${all.length} of these industries.`}
        </p>
        <div className="ind-grid">
          {all.map((name) => (
            <span className="ind-chip" key={name}>
              {name}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <p className="chart-card__cap">
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
      {rest.length > 0 && (
        <details className="ind-rest">
          <summary />
          <div className="ind-grid">
            {rest.map((name) => (
              <span className="ind-chip" key={name}>
                {name}
              </span>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
