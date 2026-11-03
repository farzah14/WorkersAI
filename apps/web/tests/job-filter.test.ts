import { describe, expect, it } from "vitest";
import { bucketForScore } from "@/lib/jobs/buckets";
import {
  applyMatchFilters,
  defaultMatchFilters,
  parseMatchFilters,
  sortMatchesDefault,
  toExportFilters,
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
  it("uses the updated match buckets", () => {
    expect(bucketForScore(95)).toBe("best");
    expect(bucketForScore(90)).toBe("best");
    expect(bucketForScore(85)).toBe("strong");
    expect(bucketForScore(71)).toBe("strong");
    expect(bucketForScore(70)).toBe("potential");
    expect(bucketForScore(50)).toBe("potential");
    expect(bucketForScore(49)).toBe("low");
  });

  it("draws bucket boundaries at 90, 71 and 50", () => {
    expect(bucketForScore(90)).toBe("best");
    expect(bucketForScore(89)).toBe("strong");
    expect(bucketForScore(71)).toBe("strong");
    expect(bucketForScore(70)).toBe("potential");
    expect(bucketForScore(50)).toBe("potential");
    expect(bucketForScore(49)).toBe("low");
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
      query: "",
      region: "global",
      workMode: "remote",
      employmentType: "all",
      sourceName: null,
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
describe("expanded result filter contract", () => {
  it("normalizes query text with NFC, whitespace collapse, and lowercase", () => {
    const decomposed = "  Caf\u0065\u0301   ENGINEER  ";
    const parsed = parseMatchFilters({ query: decomposed });
    expect(parsed?.query).toBe("caf\u00e9 engineer");
  });

  it("treats composed and decomposed spellings as equal after NFC", () => {
    const composed = parseMatchFilters({ query: "caf\u00e9" });
    const decomposed = parseMatchFilters({ query: "cafe\u0301" });
    expect(composed?.query).toBe(decomposed?.query);
  });

  it("bounds query length to 200 Unicode code points", () => {
    expect(parseMatchFilters({ query: "a".repeat(200) })).not.toBeNull();
    expect(parseMatchFilters({ query: "a".repeat(201) })).toBeNull();
    expect(parseMatchFilters({ query: "😀".repeat(200) })).not.toBeNull();
    expect(parseMatchFilters({ query: "😀".repeat(201) })).toBeNull();
    expect(parseMatchFilters({ query: 42 })).toBeNull();
  });

  it("accepts canonical employment types and rejects unknown values", () => {
    expect(parseMatchFilters({ employment_type: "full-time" })?.employmentType).toBe("full-time");
    expect(parseMatchFilters({ employment_type: "internship" })?.employmentType).toBe("internship");
    expect(parseMatchFilters({ employment_type: "permanent" })).toBeNull();
    expect(parseMatchFilters({ employment_type: "all" })).toBeNull();
  });

  it("preserves exact source names while rejecting blank or oversized values", () => {
    expect(parseMatchFilters({ source_name: "Greenhouse" })?.sourceName).toBe("Greenhouse");
    expect(parseMatchFilters({ source_name: "greenhouse" })?.sourceName).toBe("greenhouse");
    expect(parseMatchFilters({ source_name: "" })).toBeNull();
    expect(parseMatchFilters({ source_name: "   " })).toBeNull();
    expect(parseMatchFilters({ source_name: "s".repeat(200) })).not.toBeNull();
    expect(parseMatchFilters({ source_name: "s".repeat(201) })).toBeNull();
  });

  it("rejects reversed publication date ranges", () => {
    expect(parseMatchFilters({ date_from: "2026-08-31", date_to: "2026-08-01" })).toBeNull();
    expect(parseMatchFilters({ date_from: "2026-08-01", date_to: "2026-08-01" })).not.toBeNull();
  });

  it("matches query as a case-insensitive literal substring in title or company", () => {
    const rows = [
      row({ jobId: "title", title: "Engineer", company: "Other" }),
      row({ jobId: "company", title: "Analyst", company: "ACME Labs" }),
      row({ jobId: "none", title: "Analyst", company: "Other" }),
    ];
    const filters = { ...defaultMatchFilters(), query: "acme" };
    expect(applyMatchFilters(rows, filters).map((r) => r.jobId)).toEqual(["company"]);
    expect(
      applyMatchFilters(rows, { ...defaultMatchFilters(), query: "engineer" }).map((r) => r.jobId),
    ).toEqual(["title"]);
  });

  it("combines query, source, and employment type with AND semantics", () => {
    const rows = [
      row({ jobId: "match", title: "Engineer", company: "ACME", sourceName: "greenhouse", employmentType: "full-time" }),
      row({ jobId: "wrong-source", title: "Engineer", company: "ACME", sourceName: "lever", employmentType: "full-time" }),
      row({ jobId: "wrong-type", title: "Engineer", company: "ACME", sourceName: "greenhouse", employmentType: "contract" }),
      row({ jobId: "wrong-query", title: "Designer", company: "Other", sourceName: "greenhouse", employmentType: "full-time" }),
    ];
    const result = applyMatchFilters(rows, {
      ...defaultMatchFilters(),
      query: "acme",
      sourceName: "greenhouse",
      employmentType: "full-time",
    });
    expect(result.map((r) => r.jobId)).toEqual(["match"]);
  });

  it("excludes unknown metadata when an explicit field filter is selected", () => {
    const rows = [
      row({ jobId: "unknown", workMode: null, employmentType: null, publishedAt: null }),
      row({ jobId: "known", workMode: "remote", employmentType: "full-time", publishedAt: "2026-08-10T00:00:00Z" }),
    ];
    expect(
      applyMatchFilters(rows, {
        ...defaultMatchFilters(),
        workMode: "remote",
        employmentType: "full-time",
        dateFrom: "2026-08-01",
      }).map((r) => r.jobId),
    ).toEqual(["known"]);
  });

  it("hides ignored rows by default and includes them only when explicitly selected", () => {
    const rows = [
      row({ jobId: "ignored", status: "ignored" }),
      row({ jobId: "active", status: "new" }),
    ];
    expect(applyMatchFilters(rows, defaultMatchFilters()).map((r) => r.jobId)).toEqual(["active"]);
    expect(
      applyMatchFilters(rows, { ...defaultMatchFilters(), status: "ignored" }).map((r) => r.jobId),
    ).toEqual(["ignored"]);
  });

  it("does not fold German sharp s or remove accents from queries", () => {
    const rows = [row({ jobId: "strasse", title: "Stra\u00dfe Engineer" })];
    expect(
      applyMatchFilters(rows, { ...defaultMatchFilters(), query: "strasse" }).map((r) => r.jobId),
    ).toEqual([]);
  });

  it("matches composed and decomposed accented query and title equally", () => {
    const rows = [
      row({ jobId: "composed", title: "Caf\u00e9 Engineer" }),
      row({ jobId: "decomposed", title: "Cafe\u0301 Engineer" }),
    ];
    expect(
      applyMatchFilters(rows, { ...defaultMatchFilters(), query: "cafe\u0301" }).map((r) => r.jobId),
    ).toEqual(["composed", "decomposed"]);
  });

  it("serializes dashboard selections into the export wire contract", () => {
    const filters = {
      ...defaultMatchFilters(),
      query: "engineer",
      region: "global" as const,
      workMode: "remote" as const,
      employmentType: "full-time" as const,
      sourceName: "greenhouse",
      minScore: 70,
      dateFrom: "2026-08-01",
      dateTo: "2026-08-31",
    };
    expect(toExportFilters(filters)).toEqual({
      query: "engineer",
      employment_type: ["full-time"],
      source_name: ["greenhouse"],
      work_mode: ["remote"],
      min_score: 70,
      exclude_ignored: true,
      region: ["global"],
      date_from: "2026-08-01",
      date_to: "2026-08-31",
    });
  });

  it("serializes an explicit status without the ignored exclusion", () => {
    expect(
      toExportFilters({ ...defaultMatchFilters(), status: "ignored" }),
    ).toEqual({
      status: ["ignored"],
      exclude_ignored: false,
    });
  });
});
