import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import type { Proposal } from "../lib/types";
import { closingBody, closingHeadline, sectionCta } from "../lib/fallbacks";
import { Section } from "../components/Section";
import { Reveal } from "../components/Reveal";
import { CtaButton } from "../components/CtaButton";
import { linkify } from "../lib/linkify";

function onCardMove(e: ReactPointerEvent<HTMLDivElement>) {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - rect.top}px`);
}

/**
 * The strategic conclusion — "here's the opportunity we'd recommend
 * exploring," not "register for TEG." The package details are real and
 * present, but visually secondary (a smaller card, second column) to the
 * closing recommendation itself.
 */
export function Recommendation({ p }: { p: Proposal }) {
  const pkg = p.recommended_package;
  const priced = pkg.price_line.trim().length > 0;
  const mail = `mailto:${p.contact}?subject=${encodeURIComponent(`TEG 2026 — ${p.company}`)}`;

  return (
    <Section band="dark" id="recommendation" decorated>
      <div className="rec-lead">
        <span className="eyebrow">The recommendation</span>
        <h2>{closingHeadline(p)}</h2>
        <p>{closingBody(p)}</p>
      </div>

      <div className="rec-grid">
        <Reveal direction="right">
          <div>
            <CtaButton href={mail}>{sectionCta(p, "investment")}</CtaButton>

            {p.next_steps.length > 0 && (
              <div className="rec-next">
                <div className="rec-next__label">Next steps</div>
                <ul>
                  {p.next_steps.map((s, i) => (
                    <li key={i}>{linkify(s)}</li>
                  ))}
                </ul>
              </div>
            )}

            <p style={{ marginTop: "1.75rem", fontSize: "0.92rem" }}>Contact: {p.contact}</p>
          </div>
        </Reveal>

        <Reveal>
          {/* the card's border glows toward the cursor — pure CSS, tracked
              via two custom properties updated on pointer move */}
          <div
            className="rec-card"
            onPointerMove={onCardMove}
            style={{ "--mx": "50%", "--my": "0%" } as CSSProperties}
          >
            <span className="rec-card__kicker">Suggested package</span>
            <h3>{pkg.name}</h3>
            <ul>
              {pkg.includes.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
            {priced ? (
              <>
                <div className="rec-card__price">{pkg.price_line}</div>
                {pkg.payment_plan && <div className="rec-card__pay">Payment: {pkg.payment_plan}</div>}
              </>
            ) : (
              <div className="rec-card__nostprice">
                The team will share stall options and pricing tailored to your goals.
              </div>
            )}
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
