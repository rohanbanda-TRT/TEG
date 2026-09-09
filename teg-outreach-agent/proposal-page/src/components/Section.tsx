import type { ReactNode } from "react";

export function Section({
  children,
  band = "light",
  id,
  wide = false,
  decorated = false,
}: {
  children: ReactNode;
  band?: "light" | "alt" | "dark";
  id?: string;
  /** Use the wide grid column instead of the narrower reading column —
   * for chart/card grids, which make good use of the extra room. */
  wide?: boolean;
  /** Adds the abstract dot-field pattern — the honest stand-in for imagery
   * this page doesn't have. Only meaningful on `band="dark"`. */
  decorated?: boolean;
}) {
  const cls =
    band === "alt"
      ? "section section--alt"
      : band === "dark"
        ? "section section--dark"
        : "section";
  return (
    <section className={decorated ? `${cls} dotfield` : cls} id={id}>
      <div className={wide ? "container container--wide" : "container"}>{children}</div>
    </section>
  );
}
