import type { ReactNode } from "react";
import { Icon } from "./Icon";

/**
 * The shared wrapper for a titled chart/data block. `muted` visually
 * subordinates it — for event-level facts that support the story without
 * competing with the company-specific content around them.
 */
export function ChartCard({
  title,
  caption,
  icon,
  children,
  muted = false,
}: {
  title: string;
  caption?: string;
  icon?: Parameters<typeof Icon>[0]["name"];
  children: ReactNode;
  muted?: boolean;
}) {
  return (
    <div className={muted ? "chart-card chart-card--muted" : "chart-card"}>
      <div className="chart-card__head">
        {icon && (
          <span className="ibadge" aria-hidden="true">
            <Icon name={icon} />
          </span>
        )}
        <div>
          <h3>{title}</h3>
          {caption && <p className="chart-card__cap">{caption}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}
