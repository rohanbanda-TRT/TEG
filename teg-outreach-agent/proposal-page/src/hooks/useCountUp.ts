import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";

/** 0 -> `target` over ~1.1s once `active`; snaps to `target` under reduced motion. */
export function useCountUp(target: number, active: boolean): number {
  const reduced = useReducedMotion();
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!active) return;
    if (reduced) {
      setN(target);
      return;
    }
    const start = performance.now();
    const dur = 1100;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, active, reduced]);
  return n;
}
