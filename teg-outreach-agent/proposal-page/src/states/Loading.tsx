export function Loading() {
  return (
    <div style={{ maxWidth: 600, margin: "20vh auto", padding: "0 1.25rem" }}>
      <div style={{ fontWeight: 800, color: "var(--teg-navy)", fontSize: "1.25rem" }}>
        Tech Expo Gujarat 2026
      </div>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            height: 18,
            margin: "1rem 0",
            borderRadius: 6,
            background: "linear-gradient(90deg,#eef1f7 25%,#e2e6ef 37%,#eef1f7 63%)",
            backgroundSize: "400% 100%",
            animation: "sh 1.4s ease infinite",
          }}
        />
      ))}
      <style>{`@keyframes sh{0%{background-position:100% 0}100%{background-position:-100% 0}}`}</style>
    </div>
  );
}
