export function Funnel({ steps }: { steps: [string, string][] }) {
  return (
    <div className="funnel" role="img" aria-label="The TEG mechanism, step by step">
      {steps.map(([label, sub], i) => {
        const width = 100 - (i / steps.length) * 46;
        return (
          <div
            className="funnel__band"
            key={i}
            style={{ width: `${width}%`, opacity: 0.94 - i * 0.1 }}
          >
            <b>{label}</b>
            <span>{sub}</span>
          </div>
        );
      })}
    </div>
  );
}
