import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import InsightsPage from "@/app/dashboard/insights/page";

describe("Dashboard InsightsPage", () => {
  it("displays bucket percentage ranges matching domain bucket thresholds", async () => {
    const page = await InsightsPage();
    render(page);

    expect(screen.getByText("90% - 100%")).toBeInTheDocument();
    expect(screen.getByText("80% - 89%")).toBeInTheDocument();
    expect(screen.getByText("70% - 79%")).toBeInTheDocument();
    expect(screen.getByText("< 70%")).toBeInTheDocument();
  });
});
