import { motion } from "framer-motion";

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
    <motion.a
      className={variant === "ghost" ? "cta cta--ghost" : "cta"}
      href={href}
      target="_blank"
      rel="noopener"
      whileHover={{ y: -3, scale: 1.015 }}
      whileTap={{ scale: 0.97, y: 0 }}
      transition={{ type: "spring", stiffness: 400, damping: 22 }}
    >
      {children}
    </motion.a>
  );
}
