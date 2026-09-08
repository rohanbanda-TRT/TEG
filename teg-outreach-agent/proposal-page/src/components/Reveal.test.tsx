import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Reveal } from "./Reveal";

describe("Reveal", () => {
  it("renders children", () => {
    render(
      <Reveal>
        <p>hello</p>
      </Reveal>,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("renders as the given tag, for valid nesting inside lists", () => {
    const { container } = render(
      <ol>
        <Reveal as="li" className="plan-step">
          <span>step one</span>
        </Reveal>
      </ol>,
    );
    const li = container.querySelector("li.plan-step");
    expect(li).toBeInTheDocument();
    expect(li?.textContent).toBe("step one");
  });
});
