import { motion } from "framer-motion";
import type { SectorFitRow } from "../../lib/types";
import { useReveal } from "../../hooks/useReveal";

const W = 520;

export function SectorFitBars({ rows }: { rows: SectorFitRow[] }) {
  const { ref, shown } = useReveal();
  const rowH = 32;
  const h = rows.length * rowH + 8;
  const inner = W - 170;
  return (
    <div ref={ref}>
      <svg
        viewBox={`0 0 ${W} ${h}`}
        width="100%"
        role="img"
        aria-label="How TEG's levers weigh for your sector"
      >
        {rows.map((r, i) => {
          const w = Math.max(1, Math.min(5, r.weight)) / 5;
          const y = i * rowH + 4;
          return (
            <g key={r.lever}>
              <text x={0} y={y + 15} fontSize={10} fill="#64748b">
                {r.lever}
              </text>
              <motion.rect
                x={150}
                y={y + 3}
                height={15}
                rx={2}
                fill="#17b3c9"
                initial={{ width: 0 }}
                animate={shown ? { width: inner * w } : {}}
                transition={{ duration: 0.6, delay: i * 0.08 }}
              />
              <text x={150 + inner * w + 6} y={y + 15} fontSize={9} fill="#64748b">
                {Math.max(1, Math.min(5, r.weight))}/5
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
