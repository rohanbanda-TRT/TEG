export function Loading() {
  return (
    <div
      style={{
        maxWidth: 600,
        margin: "20vh auto",
        padding: "0 1.25rem",
        fontFamily: "var(--font, sans-serif)",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-display, serif)",
          fontWeight: 600,
          color: "var(--navy, #131a3a)",
          fontSize: "1.3rem",
        }}
      >
        Tech Expo Gujarat 2026
      </div>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            height: 18,
            margin: "1rem 0",
            borderRadius: 6,
            background: "linear-gradient(90deg,#f1ede3 25%,#e5e0d3 37%,#f1ede3 63%)",
            backgroundSize: "400% 100%",
            animation: "sh 1.4s ease infinite",
            opacity: 1 - i * 0.15,
          }}
        />
      ))}
      <style>{`@keyframes sh{0%{background-position:100% 0}100%{background-position:-100% 0}}`}</style>
    </div>
  );
}
