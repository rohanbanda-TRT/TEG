import { Icon } from "./Icon";

/**
 * A small icon + label/value stat — sector, focus, prepared-for, whatever
 * gives the reader an "opportunity indicator" at a glance. `value` wraps
 * freely so a long sector name or company detail never gets clipped, and
 * the whole chip disappears if there's nothing to show.
 */
export function Metric({
  icon,
  label,
  value,
  light = false,
}: {
  icon: Parameters<typeof Icon>[0]["name"];
  label: string;
  value: string;
  light?: boolean;
}) {
  if (!value) return null;
  return (
    <div className={light ? "chip chip--light" : "chip"}>
      <span className={light ? "ibadge ibadge--sm" : "ibadge ibadge--sm ibadge--dark"}>
        <Icon name={icon} size={16} />
      </span>
      <span>
        <span className="chip__label">{label}</span>
        <span className="chip__value">{value}</span>
      </span>
    </div>
  );
}
