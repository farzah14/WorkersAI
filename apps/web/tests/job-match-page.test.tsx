import { beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

const createClientMock = vi.hoisted(() => vi.fn());
const notFoundMock = vi.hoisted(() => vi.fn(() => {
  throw new Error("NEXT_NOT_FOUND");
}));
const redirectMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/server", () => ({ createClient: createClientMock }));
vi.mock("next/navigation", () => ({ notFound: notFoundMock, redirect: redirectMock }));
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn().mockResolvedValue((key: string) => key),
}));
vi.mock("@/components/jobs/job-actions", () => ({
  JobActions: () => null,
}));
vi.mock("@/components/jobs/score-badge", () => ({
  ScoreBadge: () => null,
}));
vi.mock("@/components/dashboard/dashboard-shell", () => ({
  DashboardShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import JobMatchPage from "@/app/jobs/[matchId]/page";

function setupJobMatchPage(jobStatus: string) {
  const matchData = {
    id: "match-123",
    overall_score: 88,
    verdict: "recommended",
    explanation: "Strong fit",
    recommendations: ["Learn Docker"],
    strengths: ["Python"],
    gaps: ["Kubernetes"],
    critical_gaps: [],
    skills_score: 90,
    experience_score: 85,
    education_score: 80,
    location_score: 95,
    seniority_score: 85,
    language_score: 100,
    job_id: "job-123",
    jobs: {
      title: "Backend Engineer",
      company: "Acme",
      location: "Jakarta",
      region: "indonesia",
      work_mode: "remote",
      employment_type: "full-time",
      published_at: "2026-11-01T00:00:00Z",
      source_name: "careers",
      original_url: "https://careers.acme.com/jobs/123",
      status: jobStatus,
    },
  };

  createClientMock.mockResolvedValue({
    auth: {
      getUser: vi.fn().mockResolvedValue({ data: { user: { id: "user-1" } }, error: null }),
    },
    from: vi.fn((table: string) => {
      const chain: Record<string, unknown> = {};
      chain.select = vi.fn(() => chain);
      chain.eq = vi.fn(() => chain);
      chain.maybeSingle = vi.fn(async () => {
        if (table === "job_matches") {
          return { data: matchData, error: null };
        }
        if (table === "user_jobs") {
          return { data: { status: "new" }, error: null };
        }
        return { data: null, error: null };
      });
      return chain;
    }),
  });
}

describe("JobMatchPage active status filtering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls notFound when the job status is expired", async () => {
    setupJobMatchPage("expired");

    await expect(JobMatchPage({ params: Promise.resolve({ matchId: "match-123" }) })).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );
    expect(notFoundMock).toHaveBeenCalled();
  });

  it("calls notFound when the job status is closed", async () => {
    setupJobMatchPage("closed");

    await expect(JobMatchPage({ params: Promise.resolve({ matchId: "match-123" }) })).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );
    expect(notFoundMock).toHaveBeenCalled();
  });

  it("renders when the job status is active", async () => {
    setupJobMatchPage("active");

    const element = await JobMatchPage({ params: Promise.resolve({ matchId: "match-123" }) });
    expect(notFoundMock).not.toHaveBeenCalled();
    const { getByText } = render(element);
    expect(getByText("Backend Engineer")).toBeDefined();
  });
});
