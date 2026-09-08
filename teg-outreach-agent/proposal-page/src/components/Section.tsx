import type { ReactNode } from "react";

export function Section({
  children,
  band = "light",
  id,
  wide = false,
}: {
  children: ReactNode;
  band?: "light" | "alt" | "dark";
  id?: string;
  /** Use the wide grid column instead of the narrower reading column —
   * for chart/card grids, which make good use of the extra room. */
  wide?: boolean;
}) {
  const cls =
    band === "alt"
      ? "section section--alt"
      : band === "dark"
        ? "section section--dark"
        : "section";
  return (
    <section className={cls} id={id}>
      <div className={wide ? "container container--wide" : "container"}>{children}</div>
    </section>
  );
}
