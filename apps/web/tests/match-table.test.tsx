import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MatchTable } from "@/components/jobs/match-table";
import type { MatchRow } from "@/lib/jobs/filter";

const match: MatchRow = {
  matchId: "match-1",
  jobId: "job-1",
  title: "Security Analyst",
  company: "Example Co",
  location: "Remote",
  region: "global",
  workMode: "remote",
  employmentType: "Full-time",
  publishedAt: "2026-09-11T00:00:00Z",
  sourceName: "Tavily",
  originalUrl: "https://example.com/jobs/1",
  overallScore: 75,
  status: "new",
};

describe("MatchTable", () => {
  it("does not expose discovery sources in the matches table", () => {
    render(<MatchTable rows={[match]} />);

    expect(screen.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    expect(screen.queryByText("Tavily")).not.toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(8);
  });

  it("spans every visible column when there are no matches", () => {
    render(<MatchTable rows={[]} />);

    expect(screen.getByText("No matches match the current filters.")).toHaveAttribute("colspan", "8");
  });
});
