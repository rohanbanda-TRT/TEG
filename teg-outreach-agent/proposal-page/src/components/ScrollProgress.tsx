import { motion, useScroll, useSpring } from "framer-motion";

/** A bar that fills as the reader scrolls the page. `variant="header"` styles
 * it as the hairline under the persistent proposal header instead of a
 * full-width bar of its own. */
export function ScrollProgress({ variant = "standalone" }: { variant?: "standalone" | "header" }) {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 200, damping: 32, mass: 0.2 });
  return (
    <motion.div
      className={variant === "header" ? "pnav__progress" : "scroll-progress"}
      style={{ scaleX }}
      aria-hidden="true"
    />
  );
}
