import { StatBadge } from "../StatBadge";

export function PeerStat({ names }: { names: string[] }) {
  return (
    <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", alignItems: "center" }}>
      <StatBadge value={names.length} label="companies already confirmed for TEG 2026" />
      <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", flex: 1, minWidth: 200 }}>
        {names.map((n) => (
          <span key={n} className="card" style={{ padding: ".4rem .75rem", fontSize: ".9rem" }}>
            {n}
          </span>
        ))}
      </div>
    </div>
  );
}
