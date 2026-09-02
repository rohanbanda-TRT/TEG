import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import fixture from "../__fixtures__/proposal.json";
import type { Proposal } from "../lib/types";
import { Hero } from "./Hero";
import { Priorities } from "./Priorities";
import { TheAsk } from "./TheAsk";

const p = fixture.proposal as Proposal;

describe("sections", () => {
  it("Hero shows company + headline; falls back when headline empty", () => {
    const a = render(<Hero p={p} />);
    expect(screen.getByText(p.hero_headline!)).toBeInTheDocument();
    a.unmount();
    render(<Hero p={{ ...p, hero_headline: "" }} />);
    expect(screen.getByText(`A proposal for ${p.company}`)).toBeInTheDocument();
  });

  it("Priorities renders one card per pain; nothing when empty", () => {
    const { container, rerender } = render(<Priorities p={p} />);
    expect(container.querySelectorAll(".card").length).toBe(p.pains.length);
    rerender(<Priorities p={{ ...p, pains: [] }} />);
    expect(container.querySelector("section")).toBeNull();
  });

  it("TheAsk shows price when present, hides it when empty", () => {
    const a = render(<TheAsk p={p} />);
    expect(screen.getByText(/2,34,000/)).toBeInTheDocument();
    a.unmount();
    render(
      <TheAsk
        p={{
          ...p,
          recommended_package: { ...p.recommended_package, price_line: "", payment_plan: "" },
        }}
      />,
    );
    expect(screen.getByText(/team will share stall options/i)).toBeInTheDocument();
  });
});
