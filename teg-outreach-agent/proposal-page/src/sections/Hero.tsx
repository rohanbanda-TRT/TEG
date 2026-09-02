import { motion } from "framer-motion";
import type { Proposal } from "../lib/types";
import { heroHeadline, heroSubline } from "../lib/fallbacks";
import { CtaButton } from "../components/CtaButton";

export function Hero({
  p,
  version,
  generatedOn,
}: {
  p: Proposal;
  version?: number;
  generatedOn?: string | null;
}) {
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <section className="section section--dark hero" id="top">
      <div className="container">
        <motion.div
          className="hero__tag"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          Tech Expo Gujarat 2026 · Proposal for {p.company}
        </motion.div>
        <motion.h1
          initial={{ y: 18 }}
          animate={{ y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {heroHeadline(p)}
        </motion.h1>
        <motion.p
          className="hero__sub"
          initial={{ y: 14 }}
          animate={{ y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          {heroSubline(p)}
        </motion.p>
        <div className="hero__cta">
          <CtaButton href={mail}>Talk to the team</CtaButton>
        </div>
        <p className="hero__meta">
          Prepared for {p.person}
          {p.person_role ? `, ${p.person_role}` : ""}
          {p.sector ? `  ·  ${p.sector}` : ""}
          {version ? `  ·  v${version}` : ""}
          {generatedOn ? `  ·  ${generatedOn}` : ""}
        </p>
      </div>
    </section>
  );
}
