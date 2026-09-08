import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import fixture from "../__fixtures__/proposal.json";
import type { Proposal } from "../lib/types";
import { Hero } from "./Hero";
import { CurrentState } from "./CurrentState";
import { TEGEnablement } from "./TEGEnablement";
import { Recommendation } from "./Recommendation";

const p = fixture.proposal as Proposal;

describe("Hero", () => {
  it("shows the company + headline; falls back when headline empty", () => {
    const a = render(<Hero p={p} />);
    expect(screen.getByText(p.hero_headline!)).toBeInTheDocument();
    expect(screen.getByText(p.company, { exact: false })).toBeInTheDocument();
    a.unmount();
    render(<Hero p={{ ...p, hero_headline: "" }} />);
    expect(
      screen.getByText(`Could Tech Expo Gujarat become a growth channel for ${p.company}?`),
    ).toBeInTheDocument();
  });

  it("never puts the (unbounded-length) company name inside the pill badge", () => {
    const longName = "Very Long Enterprise Technology Solutions Private Limited";
    const { container } = render(<Hero p={{ ...p, company: longName }} />);
    const badge = container.querySelector(".hero__badge");
    expect(badge?.textContent).not.toContain(longName);
    // the name still appears, just as plain wrapping text, not inside the pill
    expect(screen.getByText(longName, { exact: false })).toBeInTheDocument();
  });
});

describe("CurrentState", () => {
  it("renders one reality item per pain plus the executive summary", () => {
    const { container } = render(<CurrentState p={p} />);
    expect(container.querySelectorAll(".reality__item").length).toBe(p.pains.length);
    expect(screen.getByText(p.executive_summary)).toBeInTheDocument();
  });

  it("renders nothing when both the summary and pains are empty", () => {
    const { container } = render(
      <CurrentState p={{ ...p, executive_summary: "", pains: [] }} />,
    );
    expect(container.querySelector("section")).toBeNull();
  });

  it("still renders the summary alone with no pains, and pains alone with no summary", () => {
    const a = render(<CurrentState p={{ ...p, pains: [] }} />);
    expect(a.container.querySelector("section")).not.toBeNull();
    expect(a.container.querySelectorAll(".reality__item").length).toBe(0);
    a.unmount();
    const b = render(<CurrentState p={{ ...p, executive_summary: "" }} />);
    expect(b.container.querySelector(".state-statement")).toBeNull();
    expect(b.container.querySelectorAll(".reality__item").length).toBe(p.pains.length);
  });
});

describe("TEGEnablement", () => {
  it("renders one connected challenge->enablement card per pain", () => {
    const { container } = render(<TEGEnablement p={p} />);
    const cards = container.querySelectorAll(".enable-card");
    expect(cards.length).toBe(p.pains.length);
    expect(cards[0].textContent).toContain(p.pains[0].pain);
    expect(cards[0].textContent).toContain(p.pains[0].teg_answer);
  });

  it("renders nothing when there are no pains", () => {
    const { container } = render(<TEGEnablement p={{ ...p, pains: [] }} />);
    expect(container.querySelector("section")).toBeNull();
  });

  it("works with 2 pains and with 6 — no fixed count assumed", () => {
    const six = Array.from({ length: 6 }, (_, i) => ({
      pain: `Pain ${i}`,
      teg_answer: `Answer ${i}`,
    }));
    const { container } = render(<TEGEnablement p={{ ...p, pains: six }} />);
    expect(container.querySelectorAll(".enable-card").length).toBe(6);
  });
});

describe("Recommendation", () => {
  it("shows price when present, hides it when empty", () => {
    const a = render(<Recommendation p={p} />);
    expect(screen.getByText(/2,34,000/)).toBeInTheDocument();
    a.unmount();
    render(
      <Recommendation
        p={{
          ...p,
          recommended_package: { ...p.recommended_package, price_line: "", payment_plan: "" },
        }}
      />,
    );
    expect(screen.getByText(/team will share stall options/i)).toBeInTheDocument();
  });

  it("renders next steps as links where a URL is present", () => {
    const { container } = render(<Recommendation p={p} />);
    expect(container.querySelector('a[href*="techexpogujarat.com"]')).toBeInTheDocument();
  });

  it("degrades cleanly with no next steps", () => {
    const { container } = render(<Recommendation p={{ ...p, next_steps: [] }} />);
    expect(container.querySelector(".rec-next")).toBeNull();
  });
});
