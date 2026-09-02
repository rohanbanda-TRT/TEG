import { useCountUp } from "../hooks/useCountUp";
import { useReveal } from "../hooks/useReveal";

export function StatBadge({ value, label }: { value: number; label: string }) {
  const { ref, shown } = useReveal();
  const n = useCountUp(value, shown);
  return (
    <div className="stat-badge" ref={ref}>
      <b>{n.toLocaleString()}</b>
      <span>{label}</span>
    </div>
  );
}
