import { type ReactNode, useEffect, useRef, useState } from "react";

/**
 * Entrance animation. The block is ALWAYS rendered and readable — it starts at
 * `data-reveal="in"` and only briefly dips to "pending" (opacity fade + rise)
 * on mount before settling back. A safety timer guarantees it returns to "in"
 * even if rAF/observer never fire (headless capture, reduced motion, etc.), so
 * content is never stuck hidden.
 */
export function Reveal({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"in" | "pending">("in");

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    setState("pending");
    let raf = 0;
    const settle = () => setState("in");
    raf = requestAnimationFrame(() => requestAnimationFrame(settle));
    const safety = window.setTimeout(settle, 400 + delay * 1000);

    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(safety);
    };
  }, [delay]);

  return (
    <div ref={ref} className="reveal" data-reveal={state} style={{ transitionDelay: `${delay}s` }}>
      {children}
    </div>
  );
}
