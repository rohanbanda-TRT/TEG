import { motion, useScroll, useSpring } from "framer-motion";

/** Thin fixed bar across the top that fills as the reader scrolls the page. */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 200, damping: 32, mass: 0.2 });
  return (
    <motion.div
      className="scroll-progress"
      style={{ scaleX }}
      aria-hidden="true"
    />
  );
}
