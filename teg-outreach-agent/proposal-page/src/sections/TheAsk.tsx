import type { Proposal } from "../lib/types";
import { closingBody, closingHeadline, sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { CtaButton } from "../components/CtaButton";

export function TheAsk({ p }: { p: Proposal }) {
  const pkg = p.recommended_package;
  const priced = pkg.price_line.trim().length > 0;
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <Section band="dark" id="the-ask">
      <Reveal>
        <h2>The ask</h2>
      </Reveal>
      <Reveal>
        <div className="card" style={{ color: "var(--teg-ink)", marginTop: "1rem" }}>
          <strong>{pkg.name}</strong>
          <ul>
            {pkg.includes.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
          {priced ? (
            <>
              <div>
                <b>{pkg.price_line}</b>
              </div>
              {pkg.payment_plan && <div>Payment: {pkg.payment_plan}</div>}
            </>
          ) : (
            <div>The team will share stall options and pricing tailored to your goals.</div>
          )}
        </div>
      </Reveal>
      {p.roi_framing && (
        <Reveal>
          <p style={{ marginTop: "1rem" }}>{p.roi_framing}</p>
        </Reveal>
      )}
      <Reveal>
        <h3 style={{ marginTop: "2rem" }}>{closingHeadline(p)}</h3>
        <p>{closingBody(p)}</p>
        <div style={{ marginTop: "1rem" }}>
          <CtaButton href={mail}>{sectionCta(p, "investment")}</CtaButton>
        </div>
      </Reveal>
    </Section>
  );
}
