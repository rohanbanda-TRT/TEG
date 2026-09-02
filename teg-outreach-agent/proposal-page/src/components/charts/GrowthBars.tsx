import { GROWTH } from "../../lib/chartData";

function Group({ label, a, b, max }: { label: string; a: number; b: number; max: number }) {
  return (
    <div className="growth-group">
      <div className="growth-group__bars">
        <div className="growth-bar">
          <span className="growth-bar__value">{a.toLocaleString()}</span>
          <span
            className="growth-bar__fill growth-bar__fill--muted reveal-barv"
            style={{ "--h": `${(a / max) * 100}%` } as React.CSSProperties}
          />
        </div>
        <div className="growth-bar">
          <span className="growth-bar__value">{b.toLocaleString()}</span>
          <span
            className="growth-bar__fill reveal-barv"
            style={{ "--h": `${(b / max) * 100}%`, "--d": "0.08s" } as React.CSSProperties}
          />
        </div>
      </div>
      <div className="growth-group__label">{label}</div>
    </div>
  );
}

export function GrowthBars() {
  const max = Math.max(GROWTH.attendees[1], GROWTH.exhibitors[1]);
  return (
    <div role="img" aria-label="TEG 2024 to 2026 growth">
      <div className="growth-chart">
        <Group label="Attendees" a={GROWTH.attendees[0]} b={GROWTH.attendees[1]} max={max} />
        <Group label="Exhibitors" a={GROWTH.exhibitors[0]} b={GROWTH.exhibitors[1]} max={max} />
      </div>
      <div className="growth-legend">
        <span>
          <i className="growth-legend__dot growth-legend__dot--muted" /> TEG 2024 (actual)
        </span>
        <span>
          <i className="growth-legend__dot" /> TEG 2026 (target)
        </span>
      </div>
    </div>
  );
}
