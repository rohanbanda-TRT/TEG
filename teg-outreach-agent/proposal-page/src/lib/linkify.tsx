/** Turns the first URL-looking substring in a line of generated copy into a
 * real link, so `next_steps` like "Book at techexpogujarat.com/..." are
 * clickable without the backend needing to emit structured link data. */
export function linkify(text: string) {
  const m = text.match(/https?:\/\/\S+|[\w.-]+\.com\/\S+/);
  if (!m) return text;
  const href = m[0].startsWith("http") ? m[0] : `https://${m[0]}`;
  return (
    <a href={href} target="_blank" rel="noopener">
      {text}
    </a>
  );
}
