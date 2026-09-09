import { motion } from "framer-motion";

/** An in-page anchor (`#section`) opens in the same tab; anything else
 * (mailto:, https://…) opens in a new one so the reader never loses the
 * proposal itself. */
function isInternalAnchor(href: string): boolean {
  return href.startsWith("#");
}

export function CtaButton({
  href,
  children,
  variant = "primary",
}: {
  href: string;
  children: string;
  variant?: "primary" | "ghost";
}) {
  const internal = isInternalAnchor(href);
  return (
    <motion.a
      className={variant === "ghost" ? "cta cta--ghost" : "cta"}
      href={href}
      target={internal ? undefined : "_blank"}
      rel={internal ? undefined : "noopener"}
      whileHover={{ y: -3, scale: 1.015 }}
      whileTap={{ scale: 0.97, y: 0 }}
      transition={{ type: "spring", stiffness: 400, damping: 22 }}
    >
      {children}
    </motion.a>
  );
}
