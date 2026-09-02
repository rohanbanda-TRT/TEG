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

  it("IndustryMix lists all 18 industries when nothing is highlighted", () => {
    const { container } = render(<IndustryMix />);
    expect(container.querySelectorAll(".ind-chip").length).toBe(18);
    expect(container.querySelectorAll(".ind-chip--on").length).toBe(0);
  });

  it("IndustryMix pulls the highlighted industries out and keeps the rest", () => {
    const { container, getByText } = render(
      <IndustryMix highlight={["Manufacturing", "Textile"]} note="Your buyers sit here." />,
    );
    const on = container.querySelectorAll(".ind-chip--on");
    expect(on.length).toBe(2);
    expect(Array.from(on).map((e) => e.textContent)).toEqual(["Manufacturing", "Textile"]);
    // highlighted ones are not repeated in the remainder
    expect(container.querySelectorAll(".ind-chip").length).toBe(18);
    expect(getByText("Your buyers sit here.")).toBeInTheDocument();
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

  it("PeerStat lists names and shows the sector count with context", () => {
    const { getByText, container } = render(
      <PeerStat names={["X", "Y", "Z"]} sector="Digital Marketing & SEO" sectorTotal={4} />,
    );
    expect(getByText("X")).toBeTruthy();
    expect(container.querySelector(".stat-ring b")?.textContent).toBe("4");
    expect(container.querySelector(".peer-stat__lead p")?.textContent).toMatch(
      /Digital Marketing & SEO exhibited at TEG 2024/,
    );
  });

  it("PeerStat clamps the count up to the number of names when sectorTotal is smaller", () => {
    const { container } = render(<PeerStat names={["A", "B", "C", "D", "E"]} sectorTotal={2} />);
    expect(container.querySelector(".stat-ring b")?.textContent).toBe("5");
  });

  it("PeerStat strips a leading count the model may have written in contextLine", () => {
    const { container } = render(
      <PeerStat
        names={["A", "B"]}
        sectorTotal={9}
        contextLine="9 companies in Fintech exhibited at TEG 2024 — including the names below."
      />,
    );
    const text = container.querySelector(".peer-stat__lead p")?.textContent ?? "";
    expect(text).toBe("9 companies in Fintech exhibited at TEG 2024 — including the names below.");
  });
});
