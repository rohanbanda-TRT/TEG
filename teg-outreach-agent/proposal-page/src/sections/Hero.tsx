import { motion } from "framer-motion";
import type { Proposal } from "../lib/types";
import { heroHeadline, heroSubline } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { CtaButton } from "../components/CtaButton";

export function Hero({ p, version, generatedOn }: { p: Proposal; version?: number; generatedOn?: string | null }) {
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <Section band="dark" id="top">
      <motion.h1
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {heroHeadline(p)}
      </motion.h1>
      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
      >
        {heroSubline(p)}
      </motion.p>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.35 }}
        style={{ marginTop: "1.5rem" }}
      >
        <CtaButton href={mail}>Talk to the team</CtaButton>
      </motion.div>
      <p style={{ opacity: 0.75, fontSize: ".85rem", marginTop: "1.5rem" }}>
        Prepared for {p.person}
        {p.person_role ? `, ${p.person_role}` : ""}
        {p.sector ? ` · ${p.sector}` : ""}
        {version ? ` · v${version}` : ""}
        {generatedOn ? ` · ${generatedOn}` : ""}
      </p>
    </Section>
  );
}
