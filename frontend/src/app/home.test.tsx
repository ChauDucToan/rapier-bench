import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "./page";

describe("HomePage", () => {
  it("renders the product name", () => {
    render(<HomePage />);
    const heading = screen.getByRole("heading", {
      name: /rapier bench/i,
      level: 1,
    });
    expect(heading).toBeDefined();
    expect(heading.textContent).toContain("Rapier Bench");
  });
});
