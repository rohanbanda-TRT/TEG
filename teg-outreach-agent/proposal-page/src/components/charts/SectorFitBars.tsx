import type { SectorFitRow } from "../../lib/types";

export function SectorFitBars({ rows }: { rows: SectorFitRow[] }) {
  return (
    <div className="chart-rows" role="img" aria-label="How TEG's levers weigh for your sector">
      {rows.map((r) => {
        const w = Math.max(1, Math.min(5, r.weight));
        return (
          <div className="chart-row" key={r.lever}>
            <span className="chart-row__label">{r.lever}</span>
            <span className="chart-row__track">
              <span
                className="chart-row__fill reveal-bar"
                style={{ "--w": `${(w / 5) * 100}%` } as React.CSSProperties}
              />
            </span>
            <span className="chart-row__value">{w}/5</span>
          </div>
        );
      })}
    </div>
  );
}
