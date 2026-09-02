import { motion } from "framer-motion";
import { GROWTH } from "../../lib/chartData";
import { useCountUp } from "../../hooks/useCountUp";
import { useReveal } from "../../hooks/useReveal";

const W = 520;
const H = 220;

function Value({ x, y, v, shown }: { x: number; y: number; v: number; shown: boolean }) {
  const n = useCountUp(v, shown);
  return (
    <text x={x} y={y} fontSize={11} textAnchor="middle" fill="#1b2a5b">
      {n.toLocaleString()}
    </text>
  );
}

export function GrowthBars() {
  const { ref, shown } = useReveal();
  const groups: [string, [number, number]][] = [
    ["Attendees", GROWTH.attendees],
    ["Exhibitors", GROWTH.exhibitors],
  ];
  const max = Math.max(GROWTH.attendees[1], GROWTH.exhibitors[1]);
  const baseY = H - 44;
  const plotH = baseY - 24;
  const gw = W / groups.length;
  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="TEG 2024 to 2026 growth">
        {groups.map(([label, [a, b]], gi) => {
          const cx = gi * gw + gw / 2;
          const bars: [number, string, number][] = [
            [a, "#64748b", -46],
            [b, "#1b2a5b", 4],
          ];
          return (
            <g key={label}>
              {bars.map(([v, fill, dx], bi) => {
                const bh = (plotH * v) / max;
                return (
                  <motion.rect
                    key={bi}
                    x={cx + dx}
                    width={38}
                    rx={2}
                    fill={fill}
                    initial={{ height: 0, y: baseY }}
                    animate={shown ? { height: bh, y: baseY - bh } : {}}
                    transition={{ duration: 0.7, delay: bi * 0.1 }}
                  />
                );
              })}
              <Value x={cx - 27} y={baseY - (plotH * a) / max - 6} v={a} shown={shown} />
              <Value x={cx + 23} y={baseY - (plotH * b) / max - 6} v={b} shown={shown} />
              <text x={cx} y={baseY + 18} fontSize={12} textAnchor="middle" fill="#64748b">
                {label}
              </text>
            </g>
          );
        })}
        <rect x={0} y={H - 14} width={10} height={10} fill="#64748b" />
        <text x={14} y={H - 5} fontSize={9} fill="#64748b">
          2024 (actual)
        </text>
        <rect x={110} y={H - 14} width={10} height={10} fill="#1b2a5b" />
        <text x={124} y={H - 5} fontSize={9} fill="#64748b">
          2026 (target)
        </text>
      </svg>
    </div>
  );
}
