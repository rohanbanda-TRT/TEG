import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GrowthOpportunity } from "./GrowthOpportunity";
import type { JourneyStage } from "../lib/types";

const STAGES: JourneyStage[] = [
  { stage: "today", title: "Where Itorix is now", points: ["Pune", "10+ years"] },
  { stage: "growth_move", title: "The next move", points: ["Gujarat market"] },
  { stage: "barrier", title: "What's in the way", points: ["No local network"] },
  { stage: "teg_opportunity", title: "What TEG opens", points: ["SME audience"] },
  { stage: "action", title: "How you'd work it", points: ["Target", "Qualify"] },
  { stage: "potential", title: "Where it leads", points: ["Gujarat pipeline"] },
];

describe("GrowthOpportunity", () => {
  it("renders nothing when the journey is empty", () => {
    const { container } = render(<GrowthOpportunity stages={[]} company="Itorix" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when undefined", () => {
    const { container } = render(<GrowthOpportunity company="Itorix" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders one card per stage, in order, with its points", () => {
    const { container, getByText } = render(
      <GrowthOpportunity stages={STAGES} company="Itorix" />,
    );
    const cards = container.querySelectorAll(".gj-stage");
    expect(cards.length).toBe(6);
    expect(cards[0].textContent).toContain("Where Itorix is now");
    expect(cards[5].textContent).toContain("Where it leads");
    expect(getByText("No local network")).toBeInTheDocument();
  });

  it("labels each stage with the new growth-narrative name", () => {
    const { getByText } = render(<GrowthOpportunity stages={STAGES} company="Itorix" />);
    expect(getByText(/Current position/i)).toBeInTheDocument();
    expect(getByText(/How TEG opens market access/i)).toBeInTheDocument();
    expect(getByText(/Where the opportunity leads/i)).toBeInTheDocument();
  });

  it("uses the company name in the section heading", () => {
    const { container } = render(<GrowthOpportunity stages={STAGES} company="Itorix" />);
    expect(container.querySelector(".sec-head")?.textContent).toContain("Itorix");
  });

  it("tolerates an unknown stage key by still rendering its content", () => {
    const odd: JourneyStage[] = [...STAGES, { stage: "mystery", title: "Extra", points: ["x"] }];
    const { container } = render(<GrowthOpportunity stages={odd} company="Itorix" />);
    expect(container.querySelectorAll(".gj-stage").length).toBe(7);
  });
});
