import { motion } from "framer-motion";
import { useReveal } from "../../hooks/useReveal";

/** A vertical stack of narrowing bands — HTML, so the labels stay legible. */
export function Funnel({ steps }: { steps: [string, string][] }) {
  const { ref, shown } = useReveal();
  return (
    <div ref={ref} className="funnel" role="img" aria-label="The TEG mechanism, step by step">
      {steps.map(([label, sub], i) => {
        const width = 100 - (i / steps.length) * 46;
        return (
          <motion.div
            className="funnel__band"
            key={i}
            style={{ width: `${width}%`, opacity: 0.92 - i * 0.12 }}
            initial={{ opacity: 0, y: 12 }}
            animate={shown ? { opacity: 0.92 - i * 0.12, y: 0 } : {}}
            transition={{ duration: 0.4, delay: i * 0.12 }}
          >
            <b>{label}</b>
            <span>{sub}</span>
          </motion.div>
        );
      })}
    </div>
  );
}
