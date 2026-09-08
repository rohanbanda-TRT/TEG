import { describe, expect, it } from "vitest";
import type { Proposal } from "./types";
import { closingBody, closingHeadline, heroHeadline, heroSubline, sectionCta } from "./fallbacks";

const base = { company: "Acme", executive_summary: "Acme does BI. It wants India." } as Proposal;

describe("fallbacks", () => {
  it("heroHeadline uses the field, else a growth-framed default", () => {
    expect(heroHeadline({ ...base, hero_headline: "Win big" })).toBe("Win big");
    expect(heroHeadline(base)).toBe(
      "Could Tech Expo Gujarat become a growth channel for Acme?",
    );
  });

  it("heroSubline uses the field, else a tentative default naming the company", () => {
    expect(heroSubline({ ...base, hero_subline: "A read on the fit." })).toBe("A read on the fit.");
    expect(heroSubline(base)).toContain("Acme");
  });

  it("sectionCta uses the map, else a fixed label", () => {
    expect(sectionCta({ ...base, section_ctas: { priorities: "Go" } }, "priorities")).toBe("Go");
    expect(sectionCta(base, "priorities")).toBe("See the opportunity");
    expect(sectionCta(base, "unknown")).toBe("Learn more");
  });

  it("closing fallbacks", () => {
    expect(closingHeadline(base)).toBe("Should we explore this opportunity further?");
    expect(closingBody(base)).toContain("Reply in the chat");
  });
});
