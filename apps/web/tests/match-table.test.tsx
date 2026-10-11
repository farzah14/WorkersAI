import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
    expect(screen.getAllByRole("columnheader")).toHaveLength(6);
  });

  it("spans every visible column when there are no matches", () => {
    render(<MatchTable rows={[]} />);

    expect(screen.getByText("No matches match the current filters.")).toHaveAttribute("colspan", "6");
  });

  it("limits to top 5 jobs by default and expands on Show more click", () => {
    const matches: MatchRow[] = Array.from({ length: 7 }, (_, i) => ({
      ...match,
      matchId: `match-${i + 1}`,
      jobId: `job-${i + 1}`,
      title: `Job ${i + 1}`,
      overallScore: 80 - i,
    }));

    render(<MatchTable rows={matches} />);

    expect(screen.getByText("Job 1")).toBeInTheDocument();
    expect(screen.getByText("Job 5")).toBeInTheDocument();
    expect(screen.queryByText("Job 6")).not.toBeInTheDocument();
    expect(screen.queryByText("Job 7")).not.toBeInTheDocument();

    const showMoreButton = screen.getByRole("button", { name: /show more/i });
    expect(showMoreButton).toHaveTextContent("Show more (2 more)");
    fireEvent.click(showMoreButton);

    expect(screen.getByText("Job 6")).toBeInTheDocument();
    expect(screen.getByText("Job 7")).toBeInTheDocument();

    const showLessButton = screen.getByRole("button", { name: /show less/i });
    fireEvent.click(showLessButton);

    expect(screen.queryByText("Job 6")).not.toBeInTheDocument();
  });

  it("removes a job from the visible table when Remove is clicked", () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ jobId: "job-1", status: "ignored" }),
    });

    render(<MatchTable rows={[match]} />);

    expect(screen.getByText("Security Analyst")).toBeInTheDocument();
    const removeButton = screen.getByRole("button", { name: /remove/i });
    fireEvent.click(removeButton);
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/job-status?job_id=job-1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(screen.queryByText("Security Analyst")).not.toBeInTheDocument();
  });
});
