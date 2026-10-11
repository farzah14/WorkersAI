import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn().mockResolvedValue((key: string) => {
    const messages: Record<string, string> = {
      "buckets.best": "Best Match",
      "buckets.strong": "Strong Match",
      "buckets.potential": "Potential",
      "buckets.low": "Low Match",
    };
    return messages[key] ?? key;
  }),
}));

import InsightsPage from "@/app/dashboard/insights/page";

describe("Dashboard InsightsPage", () => {
  it("displays bucket percentage ranges matching domain bucket thresholds", async () => {
    const page = await InsightsPage();
    render(page);

    expect(screen.getByText("90% - 100%")).toBeInTheDocument();
    expect(screen.getByText("71% - 89%")).toBeInTheDocument();
    expect(screen.getByText("50% - 70%")).toBeInTheDocument();
    expect(screen.getByText("< 50%")).toBeInTheDocument();
  });
});
