import { motion } from "framer-motion";

interface PeerStatProps {
  names: string[];
  sector?: string | null;
  sectorTotal?: number;
  contextLine?: string;
}

/**
 * Named peers WITH context. A big count in a ring, the sentence that gives the
 * number meaning beside it, and the named companies below. The count is the
 * sector's TEG 2024 participation total (>= the named list, which may be
 * truncated), so it never reads as a bare "4".
 */
export function PeerStat({ names, sector, sectorTotal, contextLine }: PeerStatProps) {
  const total = Math.max(sectorTotal ?? 0, names.length);
  // Strip any leading count the model may have written — the ring shows it.
  const line =
    contextLine?.trim().replace(/^\d[\d,]*\s+/, "") ||
    `companies in ${sector ?? "your space"} exhibited at TEG 2024 — including the names below.`;

  return (
    <div className="peer-stat">
      <div className="peer-stat__lead">
        <motion.div
          className="stat-ring"
          initial={{ opacity: 0, scale: 0.75 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, amount: 0.8 }}
          transition={{ type: "spring", stiffness: 200, damping: 15 }}
        >
          <b>{total}</b>
        </motion.div>
        <p>
          <strong>{total}</strong> {line}
        </p>
      </div>
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
    </div>
  );
}
