import { beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
const createClientMock = vi.hoisted(() => vi.fn());
const redirectMock = vi.hoisted(() => vi.fn());
const matchTableCalls = vi.hoisted(() => [] as Array<{ rows: Array<{ matchId: string; title: string }> }>);
vi.mock("@/lib/supabase/server", () => ({ createClient: createClientMock }));
vi.mock("next/navigation", () => ({ redirect: redirectMock }));
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn().mockResolvedValue((key: string) => key),
}));
vi.mock("@/components/jobs/match-table", () => ({
  MatchTable: (props: { rows: Array<{ matchId: string; title: string }> }) => {
    matchTableCalls.push(props);
    return null;
  },
}));
vi.mock("@/components/jobs/dashboard-run-controls", () => ({
  DashboardRunStatus: () => null,
  SearchRunHistory: () => null,
}));

import DashboardPage from "@/app/dashboard/page";

type EqCall = [table: string, column: string, value: unknown];

function setupDashboard(options: {
  runs: Array<{ id: string; created_at: string }>;
  matchesByRun: Record<string, Array<Record<string, unknown>>>;
}) {
  const eqCalls: EqCall[] = [];
  const matchQueries: Array<{ runId: string | null; rows: Array<Record<string, unknown>> }> = [];

  function tableChain(table: string, rows: Array<Record<string, unknown>>, single = false) {
    const filters: Record<string, unknown> = {};
    const chain: Record<string, unknown> = {};
    chain.select = vi.fn(() => chain);
    chain.eq = vi.fn((column: string, value: unknown) => {
      filters[column] = value;
      eqCalls.push([table, column, value]);
      return chain;
    });
    chain.order = vi.fn(() => chain);
    chain.limit = vi.fn(() => chain);
    chain.maybeSingle = vi.fn(async () => ({
      data: single ? (rows[0] ?? null) : null,
      error: null,
    }));
    chain.then = (resolve: (value: unknown) => unknown) => {
      if (table === "job_matches") {
        const runId = (filters.search_run_id as string | undefined) ?? null;
        matchQueries.push({
          runId,
          rows: runId ? (options.matchesByRun[runId] ?? []) : Object.values(options.matchesByRun).flat(),
        });
        return Promise.resolve({
          data: runId ? (options.matchesByRun[runId] ?? []) : Object.values(options.matchesByRun).flat(),
          error: null,
        }).then(resolve);
      }
      return Promise.resolve({ data: rows, error: null }).then(resolve);
    };
    return chain;
  }

  createClientMock.mockResolvedValue({
    auth: {
      getUser: vi.fn().mockResolvedValue({ data: { user: { id: "user-1" } }, error: null }),
    },
    from: vi.fn((table: string) => {
      if (table === "job_search_runs") {
        return tableChain(table, options.runs, true);
      }
      if (table === "job_matches") {
        return tableChain(table, []);
      }
      return tableChain(table, []);
    }),
  });

  return { eqCalls, matchQueries };
}

function matchRow(matchId: string, jobId: string, score: number, status: string = "active") {
  return {
    id: matchId,
    overall_score: score,
    verdict: "recommended",
    created_at: "2026-11-04T00:00:00Z",
    job_id: jobId,
    jobs: {
      title: "Shared Engineer",
      company: "Acme",
      location: "Jakarta",
      region: "indonesia",
      work_mode: "remote",
      employment_type: "full-time",
      published_at: "2026-11-01T00:00:00Z",
      source_name: "e2e",
      original_url: "https://example.test/jobs/shared",
      status,
    },
  };
}

describe("dashboard latest-run scope (D1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("queries matches for the authenticated user's latest run only", async () => {
    const { eqCalls, matchQueries } = setupDashboard({
      runs: [{ id: "run-latest", created_at: "2026-11-04T00:00:00Z" }],
      matchesByRun: {
        "run-latest": [matchRow("match-latest", "job-shared", 92)],
        "run-older": [matchRow("match-older", "job-shared", 70)],
      },
    });

    await DashboardPage();

    expect(eqCalls).toContainEqual(["job_matches", "user_id", "user-1"]);
    expect(eqCalls).toContainEqual(["job_matches", "search_run_id", "run-latest"]);
    expect(matchQueries).toHaveLength(1);
    expect(matchQueries[0].runId).toBe("run-latest");
    expect(matchQueries[0].rows.map((row) => row.id)).toEqual(["match-latest"]);
  });

  it("never falls back to all-history matches when a run is displayed", async () => {
    const { matchQueries } = setupDashboard({
      runs: [{ id: "run-latest", created_at: "2026-11-04T00:00:00Z" }],
      matchesByRun: {
        "run-latest": [matchRow("match-latest", "job-shared", 92)],
      },
    });

    await DashboardPage();

    expect(matchQueries.every((query) => query.runId !== null)).toBe(true);
  });

  it("omits matches where jobs.status is expired or not active", async () => {
    matchTableCalls.length = 0;
    setupDashboard({
      runs: [{ id: "run-latest", created_at: "2026-11-04T00:00:00Z" }],
      matchesByRun: {
        "run-latest": [
          matchRow("match-active", "job-1", 90, "active"),
          matchRow("match-expired", "job-2", 85, "expired"),
          matchRow("match-closed", "job-3", 80, "closed"),
        ],
      },
    });

    render(await DashboardPage());

    expect(matchTableCalls).toHaveLength(1);
    const displayedMatchIds = matchTableCalls[0].rows.map((row) => row.matchId);
    expect(displayedMatchIds).toEqual(["match-active"]);
    expect(displayedMatchIds).not.toContain("match-expired");
    expect(displayedMatchIds).not.toContain("match-closed");
  });
});
