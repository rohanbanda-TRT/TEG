import { motion, useReducedMotion } from "framer-motion";
import type { Proposal } from "../lib/types";
import { heroHeadline, heroSubline } from "../lib/fallbacks";
import { CtaButton } from "../components/CtaButton";
import { Metric } from "../components/Metric";

const PERSONA_LABEL: Record<string, string> = {
  it_tech_service: "IT & technology services",
  ai_startup: "AI / deep-tech",
  non_tech_sponsor: "Brand & sponsorship",
  visitor: "Visitor",
};

/**
 * The cover of a strategic proposal: a dark inset panel (not a full-bleed
 * viewport section) holding the company's opportunity headline, TEG as
 * supporting context, and a row of icon stats — echoing the reference's
 * hero-card composition without a fabricated "event photo" behind it; the
 * dot field + glow stand in for imagery honestly instead.
 */
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
    <section className="section hero" id="top">
      <div className="container">
        <div className="hero__panel">
          <motion.div
            className="hero__orb"
            aria-hidden="true"
            animate={reduceMotion ? undefined : { x: [0, -22, 6, 0], y: [0, 14, -10, 0] }}
            transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="hero__badge">
              <span className="hero__badge-dot" aria-hidden="true" />
              Tech Expo Gujarat · 27–29 Nov 2026
            </span>
            <p className="hero__for">
              A growth proposal for <strong>{p.company}</strong>
            </p>
          </motion.div>

          <motion.h1
            initial={{ y: 22, opacity: 0, filter: "blur(6px)" }}
            animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
            transition={{ type: "spring", stiffness: 90, damping: 18, delay: 0.08 }}
          >
            {heroHeadline(p)}
          </motion.h1>

          <motion.p
            className="hero__sub"
            initial={{ y: 16, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 100, damping: 20, delay: 0.2 }}
          >
            {heroSubline(p)}
          </motion.p>

          <motion.div
            className="hero__cta"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.32 }}
          >
            <CtaButton href={mail}>Talk to the team</CtaButton>
            <CtaButton href="#today" variant="ghost">
              See the opportunity
            </CtaButton>
          </motion.div>

          <motion.div
            className="hero__chips"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <Metric icon="target" label="Sector" value={p.sector ?? ""} />
            <Metric icon="compass" label="Focus" value={PERSONA_LABEL[p.persona] ?? p.persona} />
            <Metric
              icon="users"
              label="Prepared for"
              value={p.person_role ? `${p.person}, ${p.person_role}` : p.person}
            />
            {(version || generatedOn) && (
              <Metric
                icon="calendar"
                label="Version"
                value={[version ? `v${version}` : "", generatedOn ?? ""].filter(Boolean).join(" · ")}
              />
            )}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
