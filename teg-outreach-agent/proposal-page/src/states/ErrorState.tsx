export function ErrorState() {
  return (
    <div style={{ maxWidth: 480, margin: "22vh auto", textAlign: "center", padding: "0 1.25rem" }}>
      <div
        style={{
          fontWeight: 800,
          color: "var(--teg-navy)",
          fontSize: "1.25rem",
          marginBottom: ".5rem",
        }}
      >
        Tech Expo Gujarat 2026
      </div>
      <p>This proposal link isn't valid or has expired.</p>
      <a className="cta" href="https://www.techexpogujarat.com">
        Go to techexpogujarat.com
      </a>
    </div>
  );
}
