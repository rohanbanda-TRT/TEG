import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/proposal.json";
import type { Payload, Proposal } from "./lib/types";
import { App } from "./App";

describe("App", () => {
  it("renders the hero and a chart", () => {
    const { container } = render(<App payload={fixture as Payload} />);
    expect(screen.getByText(fixture.proposal.hero_headline)).toBeInTheDocument();
    expect(container.querySelector(".chart-rows")).toBeTruthy();
  });

  it("renders every major section for a full proposal, in narrative order", () => {
    const { container } = render(<App payload={fixture as Payload} />);
    const ids = Array.from(container.querySelectorAll("section[id]")).map((s) => s.id);
    expect(ids).toEqual([
      "top",
      "today",
      "opportunity",
      "market",
      "how-teg-helps",
      "plan",
      "outcomes",
      "recommendation",
    ]);
  });

  it("degrades cleanly to a thin proposal — every optional section just disappears", () => {
    const thin: Proposal = {
      company: "ABC",
      person: "J",
      persona: "visitor",
      pains: [],
      sector_fit: [],
      growth_journey: [],
      proof: [],
      peer_companies: [],
      target_industries: [],
      how_a_teg_plays_out: [],
      roi_framing: "",
      recommended_package: { name: "Visitor pass", price_line: "", includes: [], payment_plan: "" },
      next_steps: [],
      contact: "info@techexpogujarat.com",
      executive_summary: "",
    };
    const { container } = render(
      <App payload={{ id: "x", version: 1, generated_on: null, proposal: thin }} />,
    );
    const ids = Array.from(container.querySelectorAll("section[id]")).map((s) => s.id);
    // hero and the recommendation always render (the package is a required
    // field); everything driven by an empty array or empty string is gone —
    // including MarketOpportunity, which still gets the static industry
    // list as a prop but should not render as its own section with nothing
    // company-specific to say.
    expect(ids).toEqual(["top", "recommendation"]);
  });

  it("works with a very long company name — no pill/heading breakage assumed", () => {
    const longName =
      "Very Long Enterprise Technology Solutions and Consulting Services Private Limited";
    const withLongName = {
      ...fixture,
      proposal: { ...fixture.proposal, company: longName },
    } as unknown as Payload;
    const { container } = render(<App payload={withLongName} />);
    expect(container.querySelector(".hero__badge")?.textContent).not.toContain(longName);
    expect(screen.getAllByText(longName, { exact: false }).length).toBeGreaterThan(0);
  });
});
