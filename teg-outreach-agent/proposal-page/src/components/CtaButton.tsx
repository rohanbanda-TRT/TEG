export function CtaButton({
  href,
  children,
  variant = "primary",
}: {
  href: string;
  children: string;
  variant?: "primary" | "ghost";
}) {
  return (
    <a
      className={variant === "ghost" ? "cta cta--ghost" : "cta"}
      href={href}
      target="_blank"
      rel="noopener"
    >
      {children}
    </a>
  );
}
