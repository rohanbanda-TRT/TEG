import { motion } from "framer-motion";

export function Funnel({ steps }: { steps: [string, string][] }) {
  return (
    <div className="funnel" role="img" aria-label="The TEG mechanism, step by step">
      {steps.map(([label, sub], i) => {
        const width = 100 - (i / steps.length) * 46;
        return (
          <motion.div
            className="funnel__band"
            key={i}
            initial={{ opacity: 0, scale: 0.92 }}
            whileInView={{ opacity: 0.94 - i * 0.1, scale: 1 }}
            viewport={{ once: true, amount: 0.7 }}
            transition={{ type: "spring", stiffness: 140, damping: 18, delay: i * 0.09 }}
            style={{ width: `${width}%` }}
          >
            <b>{label}</b>
            <span>{sub}</span>
          </motion.div>
        );
      })}
    </div>
  );
}
