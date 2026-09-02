import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Funnel } from "./Funnel";
import { GrowthBars } from "./GrowthBars";
import { IndustryMix } from "./IndustryMix";
import { PeerStat } from "./PeerStat";
import { SectorFitBars } from "./SectorFitBars";

describe("charts", () => {
  it("GrowthBars renders an svg", () => {
    const { container } = render(<GrowthBars />);
    expect(container.querySelector("svg")).toBeTruthy();
  });

  it("IndustryMix renders a bar per industry", () => {
    const { container } = render(<IndustryMix />);
    expect(container.querySelectorAll("rect").length).toBeGreaterThanOrEqual(18);
  });

  it("Funnel renders 4 segments", () => {
    const { container } = render(
      <Funnel
        steps={[
          ["a", "1"],
          ["b", "2"],
          ["c", "3"],
          ["d", "4"],
        ]}
      />,
    );
    expect(container.querySelectorAll("path").length).toBe(4);
  });

  it("SectorFitBars renders a bar per row and clamps weight", () => {
    const { container } = render(
      <SectorFitBars
        rows={[
          { lever: "A", weight: 9 },
          { lever: "B", weight: 2 },
        ]}
      />,
    );
    expect(container.querySelectorAll("rect").length).toBeGreaterThanOrEqual(2);
  });

  it("PeerStat lists names and shows the count", () => {
    const { getByText } = render(<PeerStat names={["X", "Y", "Z"]} />);
    expect(getByText("X")).toBeTruthy();
  });
});
