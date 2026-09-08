import type { Payload } from "../lib/types";
import { TEG_LOGO_DATA_URI } from "../lib/brand";

/** Closing credit line — contact and next steps live in Recommendation now,
 * so this stays a short sign-off rather than repeating them. */
export function Footer({ payload }: { payload: Payload }) {
  return (
    <footer className="footer section--dark">
      <div className="container">
        <img src={TEG_LOGO_DATA_URI} alt="Tech Expo Gujarat" className="footer__logo" />
        <p className="footer__tagline">Beacon of Rising Innovation &amp; AI</p>
        <small>
          v{payload.version} · {payload.generated_on} · This is an information document, not a
          contract.
        </small>
        <small>© AIMED TECH EXPO GUJARAT LLP</small>
      </div>
    </footer>
  );
}
