import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, values?: Record<string, string | number>) => {
    const messages: Record<string, string> = {
      formLabel: "Match filters",
      query: "Search title or company",
      queryPlaceholder: "Engineer or Acme",
      region: "Region",
      allRegions: "All regions",
      indonesia: "Indonesia",
      global: "Global",
      workMode: "Work mode",
      allWorkModes: "All work modes",
      remote: "Remote",
      hybrid: "Hybrid",
      onSite: "On-site",
      employmentType: "Employment type",
      allEmploymentTypes: "All employment types",
      "full-time": "Full-time",
      "part-time": "Part-time",
      contract: "Contract",
      temporary: "Temporary",
      internship: "Internship",
      apprenticeship: "Apprenticeship",
      volunteer: "Volunteer",
      freelance: "Freelance",
      source: "Source",
      allSources: "All sources",
      status: "Status",
      allStatuses: "All statuses",
      new: "New",
      saved: "Saved",
      applied: "Applied",
      ignored: "Ignored",
      minScore: "Min score",
      dateFrom: "Published from",
      dateTo: "Published to",
      clear: "Clear filters",
      filteredCount: "Showing {shown} of {total} matching jobs.",
      unknownMetadataHint: "Jobs with missing metadata appear only when filters are set to All.",
      invalidDateRange: "The start date must be on or before the end date.",
      exportTitle: "Export these results",
      latestRunNotice: "Results are for your latest search run.",
      showMore: "Show more ({count} more)",
      showLess: "Show less",
      published: "Published",
      match: "Match",
      jobTitle: "Job title",
      companyColumn: "Company",
      location: "Location",
      actions: "Actions",
      save: "Save",
      unsave: "Unsave",
      remove: "Remove",
      removeTitle: "Remove job from search results",
    };
    const text = messages[key] ?? key;
    if (!values) return text;
    return Object.entries(values).reduce(
      (result, [name, value]) => result.replace(`{${name}}`, String(value)),
      text,
    );
  },
}));

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
  employmentType: "full-time",
  publishedAt: "2026-09-11T00:00:00Z",
  sourceName: "Tavily",
  originalUrl: "https://example.com/jobs/1",
  overallScore: 75,
  status: "new",
};

describe("MatchTable", () => {
  it("does not expose discovery sources in the matches table", () => {
    render(<MatchTable rows={[match]} emptyMessage="No matches." />);

    expect(screen.queryByRole("columnheader", { name: "Source" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(6);
    expect(screen.getByRole("combobox", { name: "Source" })).toHaveValue("");
  });

  it("keeps export requests off the results view", () => {
    render(<MatchTable rows={[match]} emptyMessage="No matches." />);

    expect(screen.queryByRole("region", { name: "Export these results" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export Excel (.xlsx)" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export PDF (.pdf)" })).not.toBeInTheDocument();
  });

  it("spans every visible column when there are no matches", () => {
    render(<MatchTable rows={[]} emptyMessage="No matches for this run." />);

    expect(screen.getByText("No matches for this run.")).toHaveAttribute("colspan", "6");
  });

  it("limits to top 5 jobs by default and expands on Show more click", () => {
    const matches: MatchRow[] = Array.from({ length: 7 }, (_, i) => ({
      ...match,
      matchId: `match-${i + 1}`,
      jobId: `job-${i + 1}`,
      title: `Job ${i + 1}`,
      overallScore: 80 - i,
    }));

    render(<MatchTable rows={matches} emptyMessage="No matches." />);

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

    render(<MatchTable rows={[match]} emptyMessage="No matches." />);

    expect(screen.getByText("Security Analyst")).toBeInTheDocument();
    const removeButton = screen.getByRole("button", { name: /remove/i });
    fireEvent.click(removeButton);
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/job-status?job_id=job-1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(screen.queryByText("Security Analyst")).not.toBeInTheDocument();
  });

  it("rolls back removed job if DELETE fails", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    });

    render(<MatchTable rows={[match]} emptyMessage="No matches." />);

    expect(screen.getByText("Security Analyst")).toBeInTheDocument();
    const removeButton = screen.getByRole("button", { name: /remove/i });
    fireEvent.click(removeButton);

    expect(await screen.findByText("Security Analyst")).toBeInTheDocument();
  });

  it("updates status filter visibility after saving a job", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ jobId: "job-1", status: "saved" }),
    });

    render(<MatchTable rows={[match]} emptyMessage="No matches." />);

    const saveButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(saveButton);
    expect(await screen.findByRole("button", { name: /unsave/i })).toBeInTheDocument();

    const statusSelect = screen.getByRole("combobox", { name: "Status" });
    fireEvent.change(statusSelect, { target: { value: "saved" } });

    expect(screen.getByText("Security Analyst")).toBeInTheDocument();
  });
});

const secondMatch: MatchRow = {
  ...match,
  matchId: "match-2",
  jobId: "job-2",
  title: "Data Analyst",
  company: "Beta Corp",
  employmentType: "contract",
  sourceName: "Greenhouse",
  overallScore: 60,
};

describe("MatchTable result filters", () => {
  it("combines query, source, and employment type filters", () => {
    render(<MatchTable rows={[match, secondMatch]} emptyMessage="Empty" />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search title or company" }), {
      target: { value: "beta" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Source" }), {
      target: { value: "Tavily" },
    });

    expect(screen.queryByText("Security Analyst")).not.toBeInTheDocument();
    expect(screen.queryByText("Data Analyst")).not.toBeInTheDocument();
  });

  it("offers sorted exact source options from all rows", () => {
    render(<MatchTable rows={[match, secondMatch]} emptyMessage="Empty" />);
    const options = Array.from(
      screen.getByRole("combobox", { name: "Source" }).querySelectorAll("option"),
    ).map((option) => option.textContent);
    expect(options).toEqual(["All sources", "Greenhouse", "Tavily"]);
  });

  it("hides ignored rows by default and shows them when selected", () => {
    const ignored = { ...match, matchId: "match-ignored", jobId: "job-ignored", status: "ignored" as const };
    render(<MatchTable rows={[match, ignored]} emptyMessage="Empty" />);
    expect(screen.getAllByText("Security Analyst")).toHaveLength(1);

    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), {
      target: { value: "ignored" },
    });
    expect(screen.getByText("Security Analyst")).toBeInTheDocument();
  });

  it("resets all filters and the visible count on Clear", () => {
    const matches: MatchRow[] = Array.from({ length: 7 }, (_, i) => ({
      ...match,
      matchId: `match-${i + 1}`,
      jobId: `job-${i + 1}`,
      title: `Job ${i + 1}`,
      overallScore: 80 - i,
    }));
    render(<MatchTable rows={matches} emptyMessage="Empty" />);
    fireEvent.click(screen.getByRole("button", { name: /show more/i }));
    expect(screen.getByText("Job 7")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("searchbox", { name: "Search title or company" }), {
      target: { value: "job 7" },
    });
    expect(screen.queryByText("Job 1")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));

    expect(screen.getByText("Job 1")).toBeInTheDocument();
    expect(screen.queryByText("Job 7")).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search title or company" })).toHaveValue("");
  });

  it("shows a date error and keeps the last valid filters", () => {
    const laterMatch = { ...secondMatch, publishedAt: "2026-09-20T00:00:00Z" };
    render(<MatchTable rows={[match, laterMatch]} emptyMessage="Empty" />);

    fireEvent.change(screen.getByLabelText("Published from"), {
      target: { value: "2026-09-11" },
    });
    fireEvent.change(screen.getByLabelText("Published to"), {
      target: { value: "2026-09-11" },
    });
    expect(screen.queryByText("Data Analyst")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Published to"), {
      target: { value: "2026-09-10" },
    });

    expect(screen.getByText("The start date must be on or before the end date.")).toBeInTheDocument();
    expect(screen.getByText("Security Analyst")).toBeInTheDocument();
    expect(screen.queryByText("Data Analyst")).not.toBeInTheDocument();
  });

});
