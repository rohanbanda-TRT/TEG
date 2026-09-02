import { motion } from "framer-motion";
import { useReveal } from "../../hooks/useReveal";

const W = 520;

export function Funnel({ steps }: { steps: [string, string][] }) {
  const { ref, shown } = useReveal();
  const stepH = 52;
  const h = steps.length * stepH + 8;
  const topW = W - 40;
  const botW = W * 0.34;
  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${h}`} width="100%" role="img" aria-label="TEG mechanism funnel">
        {steps.map(([label, sub], i) => {
          const y = i * stepH + 4;
          const wTop = topW - ((topW - botW) * i) / steps.length;
          const wBot = topW - ((topW - botW) * (i + 1)) / steps.length;
          const xTop = (W - wTop) / 2;
          const xBot = (W - wBot) / 2;
          const d = `M${xTop},${y} L${xTop + wTop},${y} L${xBot + wBot},${y + stepH - 6} L${xBot},${y + stepH - 6} Z`;
          return (
            <g key={i}>
              <motion.path
                d={d}
                fill="#1b2a5b"
                opacity={0.9 - i * 0.13}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={shown ? { pathLength: 1, opacity: 0.9 - i * 0.13 } : {}}
                transition={{ duration: 0.5, delay: i * 0.12 }}
              />
              <text x={W / 2} y={y + 22} fontSize={12} fill="#fff" textAnchor="middle">
                {label}
              </text>
              <text x={W / 2} y={y + 37} fontSize={9} fill="#e2e8f0" textAnchor="middle">
                {sub}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
