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
});
