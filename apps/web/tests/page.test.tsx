import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";

describe("Home", () => {
  it("renders the InkFlow placeholder heading", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: "InkFlow" })).toBeDefined();
  });
});
