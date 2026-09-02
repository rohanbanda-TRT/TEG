import { StatBadge } from "../StatBadge";

export function PeerStat({ names }: { names: string[] }) {
  return (
    <div style={{ display: "flex", gap: "1.75rem", flexWrap: "wrap", alignItems: "center" }}>
      <StatBadge value={names.length} label="companies already confirmed for TEG 2026" />
      <div className="peer-grid" style={{ flex: 1, minWidth: 220 }}>
        {names.map((n) => (
          <span key={n}>{n}</span>
        ))}
      </div>
    </div>
  );
}
