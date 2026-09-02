import { motion } from "framer-motion";
import { INDUSTRIES } from "../../lib/chartData";
import { useReveal } from "../../hooks/useReveal";

const W = 520;

export function IndustryMix() {
  const { ref, shown } = useReveal();
  const rowH = 20;
  const h = INDUSTRIES.length * rowH + 12;
  return (
    <div ref={ref}>
      <p style={{ fontSize: ".85rem", color: "#64748b" }}>
        Buyers attend across every sector — illustrative, not to scale
      </p>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label="Industries represented">
        {INDUSTRIES.map((name, i) => {
          const y = i * rowH + 4;
          const frac = 0.55 + (0.4 * i) / (INDUSTRIES.length - 1);
          return (
            <g key={name}>
              <text x={124} y={y + 11} fontSize={10} textAnchor="end" fill="#64748b">
                {name}
              </text>
              <motion.rect
                x={132}
                y={y}
                height={13}
                rx={2}
                fill="#17b3c9"
                opacity={0.85}
                initial={{ width: 0 }}
                animate={shown ? { width: (W - 142) * frac } : {}}
                transition={{ duration: 0.5, delay: i * 0.03 }}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
