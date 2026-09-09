/**
 * A small, hand-drawn stroke-icon set — consistent weight and corner
 * treatment, single-color (currentColor) so it always matches the teal
 * badge it sits in. No icon library dependency: this page needs about a
 * dozen glyphs total, not a few hundred.
 */
const PATHS: Record<string, string> = {
  calendar:
    "M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-13Z M4 9.5h16 M8 3v3 M16 3v3",
  users:
    "M8.5 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M3.5 19.5c.7-3 2.6-4.7 5-4.7s4.3 1.7 5 4.7 M16 8a2.6 2.6 0 1 1 0 5.2 M15 14.8c1.9.4 3.2 1.9 3.7 4.2",
  chart:
    "M4 20V10 M10 20V4 M16 20v-7 M4 20h16",
  target:
    "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
  handshake:
    "M3.5 12.5 8 8l3 2 3-2 4.5 4.5 M3.5 12.5 7 16h3l1.5 1.8a1.6 1.6 0 0 0 2.4-2.1 M20.5 12.5 17 16h-3",
  pin:
    "M12 21s-6.5-5.7-6.5-10.8A6.5 6.5 0 0 1 12 3.5a6.5 6.5 0 0 1 6.5 6.7C18.5 15.3 12 21 12 21Z M12 12.7a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6Z",
  spark:
    "M12 3v4 M12 17v4 M3 12h4 M17 12h4 M5.6 5.6l2.8 2.8 M15.6 15.6l2.8 2.8 M18.4 5.6l-2.8 2.8 M8.4 15.6l-2.8 2.8",
  check: "M5 12.5 9.5 17 19 6.5",
  arrow: "M4 12h15 M13 6l6 6-6 6",
  compass:
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M15 9l-2 5-5 2 2-5 5-2Z",
  route:
    "M5 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z M19 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z M6.8 17.2 12 9.5a3 3 0 0 1 2.5-1.3H17",
  layers:
    "M12 3.5 20.5 8 12 12.5 3.5 8 12 3.5Z M3.5 12l8.5 4.5 8.5-4.5 M3.5 16l8.5 4.5 8.5-4.5",
};

export function Icon({ name, size = 20 }: { name: keyof typeof PATHS; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
