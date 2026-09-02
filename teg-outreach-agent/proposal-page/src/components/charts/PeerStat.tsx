interface PeerStatProps {
  names: string[];
  sector?: string | null;
  sectorTotal?: number;
  contextLine?: string;
}

/**
 * Named peers WITH context. A big count in a ring, the sentence that gives the
 * number meaning beside it, and the named companies below. The count is the
 * sector's TEG 2024 participation total (>= the named list, which may be
 * truncated), so it never reads as a bare "4".
 */
export function PeerStat({ names, sector, sectorTotal, contextLine }: PeerStatProps) {
  const total = Math.max(sectorTotal ?? 0, names.length);
  // Strip any leading count the model may have written — the ring shows it.
  const line =
    contextLine?.trim().replace(/^\d[\d,]*\s+/, "") ||
    `companies in ${sector ?? "your space"} exhibited at TEG 2024 — including the names below.`;

  return (
    <div className="peer-stat">
      <div className="peer-stat__lead">
        <div className="stat-ring">
          <b>{total}</b>
        </div>
        <p>
          <strong>{total}</strong> {line}
        </p>
      </div>
      <div className="peer-grid">
        {names.map((n) => (
          <span key={n}>{n}</span>
        ))}
      </div>
    </div>
  );
}
