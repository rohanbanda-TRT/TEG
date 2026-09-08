import { type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

const DIRECTION_OFFSET: Record<string, { x?: number; y?: number }> = {
  up: { y: 28 },
  left: { x: 28 },
  right: { x: -28 },
  none: {},
};

/**
 * Scroll-triggered entrance. Content is always in the DOM and readable — it
 * only animates in the first time it crosses into view (`viewport once`), so
 * there's no risk of it getting stuck hidden if the observer never fires.
 * Spring physics, not linear easing: it settles with a touch of overshoot
 * rather than a mechanical ease-out.
 */
export function Reveal({
  children,
  delay = 0,
  direction = "up",
}: {
  children: ReactNode;
  delay?: number;
  direction?: "up" | "left" | "right" | "none";
}) {
  const reduceMotion = useReducedMotion();
  const offset = DIRECTION_OFFSET[direction] ?? DIRECTION_OFFSET.up;

  if (reduceMotion) {
    return <div>{children}</div>;
  }

  return (
    <motion.div
      initial={{ opacity: 0, ...offset, filter: "blur(4px)" }}
      whileInView={{ opacity: 1, x: 0, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ type: "spring", stiffness: 120, damping: 20, delay }}
    >
      {children}
    </motion.div>
  );
}

/** Wraps a list so its children cascade in one after another. */
export function Stagger({
  children,
  step = 0.09,
}: {
  children: ReactNode;
  step?: number;
}) {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.2 }}
      variants={{ hidden: {}, show: { transition: { staggerChildren: step } } }}
    >
      {children}
    </motion.div>
  );
}

export const staggerItem = {
  hidden: { opacity: 0, y: 22, filter: "blur(3px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { type: "spring" as const, stiffness: 130, damping: 20 },
  },
};
