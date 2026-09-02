import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Funnel } from "./Funnel";
import { GrowthBars } from "./GrowthBars";
import { IndustryMix } from "./IndustryMix";
import { PeerStat } from "./PeerStat";
import { SectorFitBars } from "./SectorFitBars";

describe("charts", () => {
  it("GrowthBars renders both group labels and the real values", () => {
    const { getByText } = render(<GrowthBars />);
    expect(getByText("Attendees")).toBeInTheDocument();
    expect(getByText("Exhibitors")).toBeInTheDocument();
    expect(getByText("15,000")).toBeInTheDocument();
    expect(getByText("250")).toBeInTheDocument();
  });

  it("IndustryMix renders a row per industry", () => {
    const { container } = render(<IndustryMix />);
    expect(container.querySelectorAll(".chart-row").length).toBe(18);
  });

  it("Funnel renders one band per step with legible labels", () => {
    const { container, getByText } = render(
      <Funnel
        steps={[
          ["a", "1"],
          ["b", "2"],
          ["c", "3"],
          ["d", "4"],
        ]}
      />,
    );
    expect(container.querySelectorAll(".funnel__band").length).toBe(4);
    expect(getByText("a")).toBeInTheDocument();
  });

  it("SectorFitBars renders a row per lever and clamps the weight to 5/5", () => {
    const { container, getByText } = render(
      <SectorFitBars
        rows={[
          { lever: "A", weight: 9 },
          { lever: "B", weight: 2 },
        ]}
      />,
    );
    expect(container.querySelectorAll(".chart-row").length).toBe(2);
    expect(getByText("5/5")).toBeInTheDocument();
    expect(getByText("2/5")).toBeInTheDocument();
  });

  it("PeerStat lists names and shows the count", () => {
    const { getByText } = render(<PeerStat names={["X", "Y", "Z"]} />);
    expect(getByText("X")).toBeTruthy();
  });
});
