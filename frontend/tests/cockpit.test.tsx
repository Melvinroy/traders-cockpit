import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import Page from "@/app/page";

describe("Cockpit page", () => {
  it("renders cockpit shell", async () => {
    render(<Page />);
    expect(screen.getByText(/TRADER'S/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Setup Parameters/i)).toBeInTheDocument();
      expect(screen.getByText(/Trade Entry/i)).toBeInTheDocument();
      expect(screen.getByText(/Activity Log/i)).toBeInTheDocument();
    });
  });
});
