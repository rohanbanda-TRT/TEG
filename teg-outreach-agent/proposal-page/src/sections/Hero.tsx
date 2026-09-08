import { motion, useReducedMotion } from "framer-motion";
import type { Proposal } from "../lib/types";
import { heroHeadline, heroSubline } from "../lib/fallbacks";
import { CtaButton } from "../components/CtaButton";
import { TEG_LOGO_DATA_URI } from "../lib/brand";

export function Hero({
  p,
  version,
  generatedOn,
}: {
  p: Proposal;
  version?: number;
  generatedOn?: string | null;
}) {
  const reduceMotion = useReducedMotion();
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <section className="section section--dark hero grain" id="top">
      <motion.div
        className="hero__orb"
        aria-hidden="true"
        animate={
          reduceMotion
            ? undefined
            : { x: [0, -26, 8, 0], y: [0, 18, -14, 0] }
        }
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="container">
        <motion.div
          className="hero__brand"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <img src={TEG_LOGO_DATA_URI} alt="Tech Expo Gujarat" className="hero__logo" />
          <span className="hero__tag">Tech Expo Gujarat 2026 · Proposal for {p.company}</span>
        </motion.div>
        <motion.h1
          initial={{ y: 26, opacity: 0, filter: "blur(6px)" }}
          animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
          transition={{ type: "spring", stiffness: 90, damping: 18, delay: 0.08 }}
        >
          {heroHeadline(p)}
        </motion.h1>
        <motion.p
          className="hero__sub"
          initial={{ y: 18, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: "spring", stiffness: 100, damping: 20, delay: 0.22 }}
        >
          {heroSubline(p)}
        </motion.p>
        <motion.div
          className="hero__cta"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.36 }}
        >
          <CtaButton href={mail}>Talk to the team</CtaButton>
        </motion.div>
        <p className="hero__meta">
          Prepared for {p.person}
          {p.person_role ? `, ${p.person_role}` : ""}
          {p.sector ? `  ·  ${p.sector}` : ""}
          {version ? `  ·  v${version}` : ""}
          {generatedOn ? `  ·  ${generatedOn}` : ""}
        </p>
      </div>
      <div className="hero__scroll-cue" aria-hidden="true">
        <span>Scroll</span>
        <motion.svg
          width="14"
          height="20"
          viewBox="0 0 14 20"
          fill="none"
          animate={reduceMotion ? undefined : { y: [0, 5, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        >
          <rect x="1" y="1" width="12" height="18" rx="6" stroke="currentColor" strokeOpacity="0.5" />
          <circle cx="7" cy="6" r="1.6" fill="currentColor" />
        </motion.svg>
      </div>
    </section>
  );
}
