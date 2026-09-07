import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import type { Proposal } from "../lib/types";
import { closingBody, closingHeadline, sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { CtaButton } from "../components/CtaButton";

function onCardMove(e: ReactPointerEvent<HTMLDivElement>) {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - rect.top}px`);
}

export function TheAsk({ p }: { p: Proposal }) {
  const pkg = p.recommended_package;
  const priced = pkg.price_line.trim().length > 0;
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;
  return (
    <Section band="dark" id="the-ask">
      <div className="sec-head">
        <span className="eyebrow">The recommendation</span>
        <h2>The ask</h2>
      </div>

      <Reveal>
        {/* the card's border glows toward the cursor — pure CSS, tracked via
            two custom properties updated on pointer move */}
        <div
          className="ask-card"
          onPointerMove={onCardMove}
          style={{ "--mx": "50%", "--my": "0%" } as CSSProperties}
        >
          <h3>{pkg.name}</h3>
          <ul>
            {pkg.includes.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
          {priced ? (
            <>
              <div className="ask-card__price">{pkg.price_line}</div>
              {pkg.payment_plan && <div className="ask-card__pay">Payment: {pkg.payment_plan}</div>}
            </>
          ) : (
            <div className="ask-card__nostprice">
              The team will share stall options and pricing tailored to your goals.
            </div>
          )}
        </div>
      </Reveal>

      {p.roi_framing && (
        <Reveal>
          <p className="ask-roi">{p.roi_framing}</p>
        </Reveal>
      )}

      <Reveal>
        <div className="ask-close">
          <h3>{closingHeadline(p)}</h3>
          <p>{closingBody(p)}</p>
          <div style={{ marginTop: "1.5rem" }}>
            <CtaButton href={mail}>{sectionCta(p, "investment")}</CtaButton>
          </div>
        </div>
      </Reveal>
    </Section>
  );
}
