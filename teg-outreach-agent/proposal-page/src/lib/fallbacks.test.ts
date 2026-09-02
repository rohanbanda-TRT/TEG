import { describe, expect, it } from "vitest";
import type { Proposal } from "./types";
import { closingBody, closingHeadline, heroHeadline, heroSubline, sectionCta } from "./fallbacks";

const base = { company: "Acme", executive_summary: "Acme does BI. It wants India." } as Proposal;

describe("fallbacks", () => {
  it("heroHeadline uses the field, else 'A proposal for X'", () => {
    expect(heroHeadline({ ...base, hero_headline: "Win big" })).toBe("Win big");
    expect(heroHeadline(base)).toBe("A proposal for Acme");
  });

  it("heroSubline falls back to the first sentence of the summary", () => {
    expect(heroSubline(base)).toBe("Acme does BI.");
  });

  it("sectionCta uses the map, else a fixed label", () => {
    expect(sectionCta({ ...base, section_ctas: { priorities: "Go" } }, "priorities")).toBe("Go");
    expect(sectionCta(base, "priorities")).toBe("See the plan");
  });

  it("closing fallbacks", () => {
    expect(closingHeadline(base)).toBe("Let's make TEG 2026 count for Acme");
    expect(closingBody(base)).toContain("Reply in the chat");
  });
});
