export function StatBadge({ value, label }: { value: number; label: string }) {
  return (
    <div className="stat-badge">
      <b>{value.toLocaleString()}</b>
      <span>{label}</span>
    </div>
  );
}
