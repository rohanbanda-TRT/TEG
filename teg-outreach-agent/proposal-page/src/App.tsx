import "./theme.css";
import type { Payload } from "./lib/types";
import { Hero } from "./sections/Hero";
import { Priorities } from "./sections/Priorities";
import { Charts } from "./sections/Charts";
import { Journey } from "./sections/Journey";
import { TheAsk } from "./sections/TheAsk";
import { Section } from "./components/Section";

function linkify(step: string) {
  const m = step.match(/https?:\/\/\S+|[\w.-]+\.com\/\S+/);
  if (!m) return step;
  const href = m[0].startsWith("http") ? m[0] : `https://${m[0]}`;
  return (
    <a href={href} target="_blank" rel="noopener">
      {step}
    </a>
  );
}

export function App({ payload }: { payload: Payload }) {
  const p = payload.proposal;
  return (
    <>
      <Hero p={p} version={payload.version} generatedOn={payload.generated_on} />
      {p.executive_summary && (
        <Section band="light">
          <p style={{ fontSize: "1.15rem" }}>{p.executive_summary}</p>
        </Section>
      )}
      <Priorities p={p} />
      <Charts p={p} />
      <Journey p={p} />
      <TheAsk p={p} />
      <Section band="light">
        <p>
          <strong>Contact:</strong> {p.contact}
        </p>
        <ul>
          {p.next_steps.map((s, i) => (
            <li key={i}>{linkify(s)}</li>
          ))}
        </ul>
        <p style={{ fontSize: ".8rem", color: "#64748b" }}>
          v{payload.version} · {payload.generated_on} · This is an information document, not a
          contract.{" "}
          <a href={payload.pdf_url} target="_blank" rel="noopener">
            Download as PDF
          </a>
        </p>
      </Section>
    </>
  );
}
