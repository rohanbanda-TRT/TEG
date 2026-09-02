import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatBadge } from "./StatBadge";

describe("StatBadge", () => {
  it("renders the value and label", () => {
    render(<StatBadge value={15000} label="visitors" />);
    expect(screen.getByText("visitors")).toBeInTheDocument();
    expect(screen.getByText("15,000")).toBeInTheDocument();
  });
});
