import { EMPLOYMENT_TYPES } from "@/lib/search/schema";

export type JobStatus = "new" | "saved" | "applied" | "ignored";

export type RegionValue = "indonesia" | "global";

export type WorkModeValue = "on-site" | "hybrid" | "remote";

export type EmploymentType = (typeof EMPLOYMENT_TYPES)[number];

export type MatchRow = {
  matchId: string;
  jobId: string;
  title: string;
  company: string;
  location: string | null;
  region: RegionValue | "unknown";
  workMode: WorkModeValue | null;
  employmentType: string | null;
  publishedAt: string | null;
  sourceName: string;
  originalUrl: string;
  overallScore: number;
  status: JobStatus;
};

export type MatchFilters = {
  query: string;
  region: "all" | RegionValue;
  workMode: "all" | WorkModeValue;
  employmentType: "all" | EmploymentType;
  sourceName: string | null;
  minScore: number;
  status: "all" | JobStatus;
  dateFrom: string | null;
  dateTo: string | null;
};

export const MATCH_FILTER_KEYS = [
  "query",
  "region",
  "work_mode",
  "employment_type",
  "source_name",
  "min_score",
  "status",
  "date_from",
  "date_to",
] as const;

const REGIONS: ReadonlySet<string> = new Set(["indonesia", "global"]);
const WORK_MODES: ReadonlySet<string> = new Set(["on-site", "hybrid", "remote"]);
const STATUSES: ReadonlySet<string> = new Set(["new", "saved", "applied", "ignored"]);
const EMPLOYMENT_TYPE_SET: ReadonlySet<string> = new Set(EMPLOYMENT_TYPES);

const MAX_QUERY_CODE_POINTS = 200;
const MAX_SOURCE_CODE_POINTS = 200;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function isDateString(value: unknown): value is string {
  if (typeof value !== "string" || !DATE_RE.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value);
}

/**
 * Normalize query text for cross-runtime literal matching.
 *
 * Uses NFC, whitespace collapse, and JavaScript `toLowerCase()` only. This
 * intentionally does not casefold (`Straße` != `strasse`) or remove accents,
 * because the worker must apply the identical comparison.
 */
export function normalizeQuery(value: string): string {
  return value.normalize("NFC").trim().replace(/\s+/g, " ").toLowerCase();
}

function codePointLength(value: string): number {
  return Array.from(value).length;
}

export function defaultMatchFilters(): MatchFilters {
  return {
    query: "",
    region: "all",
    workMode: "all",
    employmentType: "all",
    sourceName: null,
    minScore: 0,
    status: "all",
    dateFrom: null,
    dateTo: null,
  };
}

export function parseMatchFilters(input: unknown): MatchFilters | null {
  if (input === null || typeof input !== "object" || Array.isArray(input)) return null;
  const record = input as Record<string, unknown>;
  const keys = Object.keys(record);
  if (keys.some((key) => !MATCH_FILTER_KEYS.includes(key as (typeof MATCH_FILTER_KEYS)[number]))) {
    return null;
  }

  const filters = defaultMatchFilters();

  if (record.query !== undefined) {
    if (typeof record.query !== "string") return null;
    const normalized = normalizeQuery(record.query);
    if (codePointLength(normalized) > MAX_QUERY_CODE_POINTS) return null;
    filters.query = normalized;
  }
  if (record.region !== undefined) {
    if (typeof record.region !== "string" || !REGIONS.has(record.region)) return null;
    filters.region = record.region as RegionValue;
  }
  if (record.work_mode !== undefined) {
    if (typeof record.work_mode !== "string" || !WORK_MODES.has(record.work_mode)) return null;
    filters.workMode = record.work_mode as WorkModeValue;
  }
  if (record.employment_type !== undefined) {
    if (typeof record.employment_type !== "string" || !EMPLOYMENT_TYPE_SET.has(record.employment_type)) {
      return null;
    }
    filters.employmentType = record.employment_type as EmploymentType;
  }
  if (record.source_name !== undefined) {
    if (typeof record.source_name !== "string") return null;
    const source = record.source_name.trim();
    if (!source || codePointLength(source) > MAX_SOURCE_CODE_POINTS) return null;
    filters.sourceName = source;
  }
  if (record.min_score !== undefined) {
    if (typeof record.min_score !== "number" || !Number.isInteger(record.min_score)) return null;
    if (record.min_score < 0 || record.min_score > 100) return null;
    filters.minScore = record.min_score;
  }
  if (record.status !== undefined) {
    if (typeof record.status !== "string" || !STATUSES.has(record.status)) return null;
    filters.status = record.status as JobStatus;
  }
  if (record.date_from !== undefined) {
    if (!isDateString(record.date_from)) return null;
    filters.dateFrom = record.date_from;
  }
  if (record.date_to !== undefined) {
    if (!isDateString(record.date_to)) return null;
    filters.dateTo = record.date_to;
  }
  if (filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo) {
    return null;
  }
  return filters;
}

function inDateRange(publishedAt: string | null, filters: MatchFilters): boolean {
  if (!filters.dateFrom && !filters.dateTo) return true;
  if (!publishedAt) return false;
  const publishedDay = publishedAt.slice(0, 10);
  if (filters.dateFrom && publishedDay < filters.dateFrom) return false;
  if (filters.dateTo && publishedDay > filters.dateTo) return false;
  return true;
}

function matchesQuery(row: MatchRow, query: string): boolean {
  if (!query) return true;
  return (
    normalizeQuery(row.title).includes(query) ||
    normalizeQuery(row.company).includes(query)
  );
}

export function applyMatchFilters(rows: MatchRow[], filters: MatchFilters): MatchRow[] {
  const query = normalizeQuery(filters.query);
  return rows.filter((row) => {
    // All status means the active dashboard view, which hides ignored rows.
    // Selecting Ignored explicitly is the only way to see them.
    if (filters.status === "all" && row.status === "ignored") return false;
    if (!matchesQuery(row, query)) return false;
    if (filters.region !== "all" && row.region !== filters.region) return false;
    if (filters.workMode !== "all" && row.workMode !== filters.workMode) return false;
    if (filters.employmentType !== "all" && row.employmentType !== filters.employmentType) {
      return false;
    }
    if (filters.sourceName !== null && row.sourceName !== filters.sourceName) return false;
    if (row.overallScore < filters.minScore) return false;
    if (filters.status !== "all" && row.status !== filters.status) return false;
    return inDateRange(row.publishedAt, filters);
  });
}

export function sortMatchesDefault(rows: MatchRow[]): MatchRow[] {
  return [...rows].sort((a, b) => {
    if (b.overallScore !== a.overallScore) return b.overallScore - a.overallScore;
    const aTime = a.publishedAt ? new Date(a.publishedAt).getTime() : -Infinity;
    const bTime = b.publishedAt ? new Date(b.publishedAt).getTime() : -Infinity;
    if (bTime !== aTime) return bTime - aTime;
    const byTitle = a.title.localeCompare(b.title);
    if (byTitle !== 0) return byTitle;
    return a.matchId.localeCompare(b.matchId);
  });
}
