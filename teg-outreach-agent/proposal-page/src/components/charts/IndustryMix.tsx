import { INDUSTRIES } from "../../lib/chartData";

export function IndustryMix() {
  return (
    <div>
      <p className="chart-caption">
        Buyers attend across every sector — illustrative, not to scale
      </p>
      <div className="chart-rows" role="img" aria-label="Industries represented at TEG">
        {INDUSTRIES.map((name, i) => {
          const frac = 0.5 + (0.45 * i) / (INDUSTRIES.length - 1);
          return (
            <div className="chart-row" key={name}>
              <span className="chart-row__label">{name}</span>
              <span className="chart-row__track">
                <span
                  className="chart-row__fill chart-row__fill--cyan reveal-bar"
                  style={{ "--w": `${frac * 100}%`, "--d": `${i * 0.03}s` } as React.CSSProperties}
                />
              </span>
              <span className="chart-row__value" aria-hidden="true" />
            </div>
          );
        })}
      </div>
    </div>
  );
}
