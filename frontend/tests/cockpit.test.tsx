import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import Page from "@/app/page";

describe("Cockpit page", () => {
  it("renders cockpit shell", () => {
    render(<Page />);
    expect(screen.getByText(/TRADER'S/i)).toBeInTheDocument();
    expect(screen.getByText(/Setup Parameters/i)).toBeInTheDocument();
    expect(screen.getByText(/Trade Entry/i)).toBeInTheDocument();
    expect(screen.getByText(/Activity Log/i)).toBeInTheDocument();
  });
});
