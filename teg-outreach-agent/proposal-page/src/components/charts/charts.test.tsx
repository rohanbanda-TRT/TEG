import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Funnel } from "./Funnel";
import { GrowthBars } from "./GrowthBars";
import { IndustryList } from "./IndustryList";
import { PeerStat } from "./PeerStat";
import { SectorFitBars } from "./SectorFitBars";

const INDUSTRIES = Array.from({ length: 18 }, (_, i) => `Industry ${i + 1}`);
const GROWTH_SERIES = [
  { label: "Attendees", from: 8000, to: 15000 },
  { label: "Exhibitors", from: 125, to: 250 },
];

describe("charts", () => {
  it("GrowthBars takes its series as a prop and renders labels + values", () => {
    const { getByText } = render(<GrowthBars series={GROWTH_SERIES} />);
    expect(getByText("Attendees")).toBeInTheDocument();
    expect(getByText("Exhibitors")).toBeInTheDocument();
    expect(getByText("15,000")).toBeInTheDocument();
    expect(getByText("250")).toBeInTheDocument();
  });

  it("GrowthBars renders nothing for an empty series", () => {
    const { container } = render(<GrowthBars series={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("IndustryList lists the full given list when nothing is highlighted", () => {
    const { container } = render(<IndustryList all={INDUSTRIES} />);
    expect(container.querySelectorAll(".ind-chip").length).toBe(18);
    expect(container.querySelectorAll(".ind-chip--on").length).toBe(0);
  });

  it("IndustryList pulls the highlighted industries out and tucks the rest behind a disclosure", () => {
    const { container, getByText } = render(
      <IndustryList all={INDUSTRIES} highlight={["Industry 1", "Industry 2"]} note="Your buyers sit here." />,
    );
    const on = container.querySelectorAll(".ind-chip--on");
    expect(on.length).toBe(2);
    expect(Array.from(on).map((e) => e.textContent)).toEqual(["Industry 1", "Industry 2"]);
    // the rest live inside <details>, not repeated among the highlighted chips
    const rest = container.querySelectorAll(".ind-rest .ind-chip");
    expect(rest.length).toBe(16);
    expect(getByText("Your buyers sit here.")).toBeInTheDocument();
  });

  it("IndustryList works with a short list too — no assumption of exactly 18", () => {
    const { container } = render(<IndustryList all={["A", "B", "C"]} />);
    expect(container.querySelectorAll(".ind-chip").length).toBe(3);
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
    expect(container.querySelector(".peer-count")?.textContent).toBe("4");
    expect(container.querySelector(".peer-stat__lead p")?.textContent).toMatch(
      /Digital Marketing & SEO exhibited at TEG 2024/,
    );
  });

  it("PeerStat clamps the count up to the number of names when sectorTotal is smaller", () => {
    const { container } = render(<PeerStat names={["A", "B", "C", "D", "E"]} sectorTotal={2} />);
    expect(container.querySelector(".peer-count")?.textContent).toBe("5");
  });

  it("PeerStat handles a large count without a fixed-size shape to overflow", () => {
    const { container } = render(<PeerStat names={["A"]} sectorTotal={12345} />);
    expect(container.querySelector(".peer-count")?.textContent).toBe("12,345");
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
