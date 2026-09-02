import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/proposal.json";
import type { Payload } from "./lib/types";
import { App } from "./App";

describe("App", () => {
  it("renders the hero and a chart", () => {
    const { container } = render(<App payload={fixture as Payload} />);
    expect(screen.getByText(fixture.proposal.hero_headline)).toBeInTheDocument();
    expect(container.querySelector(".chart-rows")).toBeTruthy();
  });
});
