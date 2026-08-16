import { describe, expect, it } from "vitest";
import { bucketForScore } from "@/lib/jobs/buckets";
import {
  applyMatchFilters,
  defaultMatchFilters,
  parseMatchFilters,
  sortMatchesDefault,
  type MatchFilters,
  type MatchRow,
} from "@/lib/jobs/filter";

function row(overrides: Partial<MatchRow> = {}): MatchRow {
  return {
    matchId: "match-1",
    jobId: "job-1",
    title: "Data Engineer",
    company: "Acme",
    location: "Jakarta",
    region: "indonesia",
    workMode: "hybrid",
    employmentType: "full-time",
    publishedAt: "2026-08-01T00:00:00Z",
    sourceName: "test",
    originalUrl: "https://example.test/jobs/1",
    overallScore: 75,
    status: "new",
    ...overrides,
  };
}

describe("bucketForScore", () => {
  it("uses the locked match buckets", () => {
    expect(bucketForScore(95)).toBe("best");
    expect(bucketForScore(85)).toBe("strong");
    expect(bucketForScore(75)).toBe("potential");
    expect(bucketForScore(69)).toBe("low");
  });

  it("draws bucket boundaries at 90, 80 and 70", () => {
    expect(bucketForScore(90)).toBe("best");
    expect(bucketForScore(89)).toBe("strong");
    expect(bucketForScore(80)).toBe("strong");
    expect(bucketForScore(79)).toBe("potential");
    expect(bucketForScore(70)).toBe("potential");
    expect(bucketForScore(0)).toBe("low");
  });
});

describe("parseMatchFilters", () => {
  it("accepts a valid filter object with all allowed fields", () => {
    const parsed = parseMatchFilters({
      region: "global",
      work_mode: "remote",
      min_score: 70,
      status: "saved",
      date_from: "2026-08-01",
      date_to: "2026-08-31",
    });
    expect(parsed).not.toBeNull();
    expect(parsed).toEqual({
      region: "global",
      workMode: "remote",
      minScore: 70,
      status: "saved",
      dateFrom: "2026-08-01",
      dateTo: "2026-08-31",
    });
  });

  it("defaults missing keys to the unfiltered state", () => {
    expect(parseMatchFilters({})).toEqual(defaultMatchFilters());
  });

  it("rejects unknown fields such as SQL-like injections", () => {
    expect(parseMatchFilters({ sql: "1=1" })).toBeNull();
    expect(parseMatchFilters({ min_score: "70; drop table user_jobs" })).toBeNull();
    expect(parseMatchFilters({ region: "asia" })).toBeNull();
    expect(parseMatchFilters({ work_mode: "office" })).toBeNull();
    expect(parseMatchFilters({ status: "deleted" })).toBeNull();
  });

  it("bounds min_score to an integer between 0 and 100", () => {
    expect(parseMatchFilters({ min_score: -1 })).toBeNull();
    expect(parseMatchFilters({ min_score: 101 })).toBeNull();
    expect(parseMatchFilters({ min_score: 70.5 })).toBeNull();
    expect(parseMatchFilters({ min_score: "80" })).toBeNull();
    expect(parseMatchFilters({ min_score: 0 })).not.toBeNull();
    expect(parseMatchFilters({ min_score: 100 })).not.toBeNull();
  });

  it("rejects malformed date ranges", () => {
    expect(parseMatchFilters({ date_from: "08/01/2026" })).toBeNull();
    expect(parseMatchFilters({ date_from: "2026-08-32" })).toBeNull();
    expect(parseMatchFilters({ date_to: "2026-13-01" })).toBeNull();
  });

  it("rejects non-object input", () => {
    expect(parseMatchFilters(null)).toBeNull();
    expect(parseMatchFilters("region=indonesia")).toBeNull();
    expect(parseMatchFilters([{ region: "indonesia" }])).toBeNull();
  });
});

describe("applyMatchFilters", () => {
  const rows = [
    row({
      jobId: "job-1",
      title: "Data Engineer",
      region: "indonesia",
      workMode: "hybrid",
      overallScore: 92,
      status: "new",
      publishedAt: "2026-08-10T00:00:00Z",
    }),
    row({
      jobId: "job-2",
      title: "Data Engineer II",
      region: "indonesia",
      workMode: "remote",
      overallScore: 81,
      status: "saved",
      publishedAt: "2026-08-05T00:00:00Z",
    }),
    row({
      jobId: "job-3",
      title: "Data Analyst",
      region: "global",
      workMode: "on-site",
      overallScore: 65,
      status: "applied",
      publishedAt: "2026-07-20T00:00:00Z",
    }),
    row({
      jobId: "job-4",
      title: "Data Engineer III",
      region: "global",
      workMode: "remote",
      overallScore: 73,
      status: "new",
      publishedAt: "2026-08-01T00:00:00Z",
    }),
  ];

  function filtered(partial: Partial<MatchFilters>): MatchRow[] {
    return applyMatchFilters(rows, { ...defaultMatchFilters(), ...partial });
  }

  it("keeps everything when no filters are set", () => {
    expect(filtered({})).toHaveLength(4);
  });

  it("filters by region", () => {
    expect(filtered({ region: "indonesia" }).map((r) => r.jobId)).toEqual(["job-1", "job-2"]);
    expect(filtered({ region: "global" }).map((r) => r.jobId)).toEqual(["job-3", "job-4"]);
  });

  it("filters by work mode", () => {
    expect(filtered({ workMode: "remote" }).map((r) => r.jobId)).toEqual(["job-2", "job-4"]);
  });

  it("filters by minimum score", () => {
    expect(filtered({ minScore: 80 }).map((r) => r.jobId)).toEqual(["job-1", "job-2"]);
  });

  it("filters by tracking status", () => {
    expect(filtered({ status: "new" }).map((r) => r.jobId)).toEqual(["job-1", "job-4"]);
  });

  it("filters by published date range", () => {
    expect(
      filtered({ dateFrom: "2026-08-01", dateTo: "2026-08-31" }).map((r) => r.jobId),
    ).toEqual(["job-1", "job-2", "job-4"]);
  });

  it("combines filters with AND semantics", () => {
    expect(filtered({ region: "global", workMode: "remote", minScore: 80 }).map((r) => r.jobId)).toEqual([]);
    expect(filtered({ region: "global", workMode: "remote", minScore: 70 }).map((r) => r.jobId)).toEqual(["job-4"]);
  });
});

describe("sortMatchesDefault", () => {
  it("sorts by overall score descending by default", () => {
    const rows = [
      row({ jobId: "job-a", overallScore: 70 }),
      row({ jobId: "job-b", overallScore: 95 }),
      row({ jobId: "job-c", overallScore: 88 }),
    ];
    expect(sortMatchesDefault(rows).map((r) => r.jobId)).toEqual(["job-b", "job-c", "job-a"]);
  });

  it("breaks ties by newest published date then title", () => {
    const rows = [
      row({ jobId: "job-a", overallScore: 90, publishedAt: "2026-08-01T00:00:00Z", title: "A" }),
      row({ jobId: "job-b", overallScore: 90, publishedAt: "2026-08-10T00:00:00Z", title: "B" }),
      row({ jobId: "job-c", overallScore: 90, publishedAt: "2026-08-10T00:00:00Z", title: "C" }),
      row({ jobId: "job-d", overallScore: 90, publishedAt: null, title: "D" }),
    ];
    expect(sortMatchesDefault(rows).map((r) => r.jobId)).toEqual(["job-b", "job-c", "job-a", "job-d"]);
  });

  it("does not mutate the input array", () => {
    const rows = [row({ overallScore: 70 }), row({ overallScore: 95 })];
    const copy = [...rows];
    sortMatchesDefault(rows);
    expect(rows).toEqual(copy);
  });
});