export function ErrorState() {
  return (
    <div
      style={{
        maxWidth: 480,
        margin: "22vh auto",
        textAlign: "center",
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
          marginBottom: ".6rem",
        }}
      >
        Tech Expo Gujarat 2026
      </div>
      <p>This proposal link isn't valid or has expired.</p>
      <div style={{ marginTop: "1.25rem" }}>
        <a className="cta" href="https://www.techexpogujarat.com">
          Go to techexpogujarat.com
        </a>
      </div>
    </div>
  );
}
