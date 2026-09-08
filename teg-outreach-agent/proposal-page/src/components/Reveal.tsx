import { type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

const DIRECTION_OFFSET: Record<string, { x?: number; y?: number }> = {
  up: { y: 28 },
  left: { x: 28 },
  right: { x: -28 },
  none: {},
};

// The only tags any section actually needs to reveal-as — kept as a fixed
// map (not a dynamic `motion[as]` lookup) so this stays type-safe.
const TAGS = {
  div: motion.div,
  li: motion.li,
  span: motion.span,
} as const;

/**
 * Scroll-triggered entrance. Content is always in the DOM and readable — it
 * only animates in the first time it crosses into view (`viewport once`), so
 * there's no risk of it getting stuck hidden if the observer never fires.
 * Spring physics, not linear easing: it settles with a touch of overshoot
 * rather than a mechanical ease-out.
 *
 * `as` lets this wrap an `<li>` (or other tag) directly instead of always
 * inserting a `<div>` — needed wherever the parent requires a specific child
 * tag (an `<ol>`'s children must be `<li>`) for valid, accessible markup.
 */
export function Reveal({
  children,
  delay = 0,
  direction = "up",
  as = "div",
  className,
}: {
  children: ReactNode;
  delay?: number;
  direction?: "up" | "left" | "right" | "none";
  as?: keyof typeof TAGS;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();
  const offset = DIRECTION_OFFSET[direction] ?? DIRECTION_OFFSET.up;
  const Tag = TAGS[as];

  if (reduceMotion) {
    const Plain = as;
    return <Plain className={className}>{children}</Plain>;
  }

  return (
    <Tag
      className={className}
      initial={{ opacity: 0, ...offset, filter: "blur(4px)" }}
      whileInView={{ opacity: 1, x: 0, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ type: "spring", stiffness: 120, damping: 20, delay }}
    >
      {children}
    </Tag>
  );
}
