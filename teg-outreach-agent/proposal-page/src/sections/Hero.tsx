import { motion } from "framer-motion";
import type { Proposal } from "../lib/types";
import { heroHeadline, heroSubline } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { CtaButton } from "../components/CtaButton";

export function Hero({ p, version, generatedOn }: { p: Proposal; version?: number; generatedOn?: string | null }) {
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <Section band="dark" id="top">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{
          display: "inline-block",
          fontSize: ".8rem",
          fontWeight: 600,
          letterSpacing: ".08em",
          textTransform: "uppercase",
          color: "#9be3ee",
          border: "1px solid rgba(155,227,238,.35)",
          borderRadius: 999,
          padding: ".35rem .9rem",
          marginBottom: "1.5rem",
        }}
      >
        Tech Expo Gujarat 2026 · A proposal for {p.company}
      </motion.div>
      <motion.h1
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{ maxWidth: "16ch" }}
      >
        {heroHeadline(p)}
      </motion.h1>
      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
        style={{ maxWidth: "48ch", fontSize: "1.2rem", color: "#d8e0f2" }}
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
