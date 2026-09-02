import type { ReactNode } from "react";

export function Section({
  children,
  band = "light",
  id,
}: {
  children: ReactNode;
  band?: "light" | "alt" | "dark";
  id?: string;
}) {
  const cls =
    band === "alt"
      ? "section section--alt"
      : band === "dark"
        ? "section section--dark"
        : "section";
  return (
    <section className={cls} id={id}>
      <div className="container">{children}</div>
    </section>
  );
}
