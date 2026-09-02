interface PeerStatProps {
  names: string[];
  sector?: string | null;
  sectorTotal?: number;
  contextLine?: string;
}

/**
 * Named peers WITH context. The count is the sector's TEG 2024 participation
 * total (>= the named list, which may be truncated); the context line explains
 * what the number means so it never reads as a bare "4".
 */
export function PeerStat({ names, sector, sectorTotal, contextLine }: PeerStatProps) {
  const total = Math.max(sectorTotal ?? 0, names.length);
  // Strip any leading count the model may have written — we render it ourselves.
  const tail =
    contextLine?.trim().replace(/^\d[\d,]*\s+/, "") ||
    `companies in ${sector ?? "your space"} exhibited at TEG 2024 — including the names below.`;

  return (
    <div className="peer-stat">
      <p className="peer-stat__lead">
        <b>{total}</b> {tail}
      </p>
      <div className="peer-grid">
        {names.map((n) => (
          <span key={n}>{n}</span>
        ))}
      </div>
    </div>
  );
}
