import { motion } from "framer-motion";

interface PeerStatProps {
  names: string[];
  sector?: string | null;
  sectorTotal?: number;
  contextLine?: string;
}

/**
 * Named peers WITH context. A big number (not a fixed-size ring — a ring
 * sized for "12" breaks on a 4-digit count) plus the sentence that gives it
 * meaning, and the named companies below.
 */
export function PeerStat({ names, sector, sectorTotal, contextLine }: PeerStatProps) {
  const total = Math.max(sectorTotal ?? 0, names.length);
  // Strip any leading count the model may have written — the number above does that job.
  const line =
    contextLine?.trim().replace(/^\d[\d,]*\s+/, "") ||
    `companies in ${sector ?? "your space"} exhibited at TEG 2024 — including the names below.`;

  return (
    <div className="peer-stat">
      <div className="peer-stat__lead">
        <motion.span
          className="peer-count"
          initial={{ opacity: 0, y: 8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.8 }}
          transition={{ type: "spring", stiffness: 200, damping: 20 }}
        >
          {total.toLocaleString()}
        </motion.span>
        <p>
          <strong>{total.toLocaleString()}</strong> {line}
        </p>
      </div>
      {names.length > 0 && (
        <div className="peer-grid">
          {names.map((n, i) => (
            <motion.span
              key={n}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.8 }}
              transition={{ type: "spring", stiffness: 180, damping: 18, delay: i * 0.04 }}
            >
              {n}
            </motion.span>
          ))}
        </div>
      )}
    </div>
  );
}
