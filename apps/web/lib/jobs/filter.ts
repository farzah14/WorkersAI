export type JobStatus = "new" | "saved" | "applied" | "ignored";

export type RegionValue = "indonesia" | "global";

export type WorkModeValue = "on-site" | "hybrid" | "remote";

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
  region: "all" | RegionValue;
  workMode: "all" | WorkModeValue;
  minScore: number;
  status: "all" | JobStatus;
  dateFrom: string | null;
  dateTo: string | null;
};

export const MATCH_FILTER_KEYS = [
  "region",
  "work_mode",
  "min_score",
  "status",
  "date_from",
  "date_to",
] as const;

const REGIONS: ReadonlySet<string> = new Set(["indonesia", "global"]);
const WORK_MODES: ReadonlySet<string> = new Set(["on-site", "hybrid", "remote"]);
const STATUSES: ReadonlySet<string> = new Set(["new", "saved", "applied", "ignored"]);

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function isDateString(value: unknown): value is string {
  if (typeof value !== "string" || !DATE_RE.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value);
}

export function defaultMatchFilters(): MatchFilters {
  return {
    region: "all",
    workMode: "all",
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

  if (record.region !== undefined) {
    if (typeof record.region !== "string" || !REGIONS.has(record.region)) return null;
    filters.region = record.region as RegionValue;
  }
  if (record.work_mode !== undefined) {
    if (typeof record.work_mode !== "string" || !WORK_MODES.has(record.work_mode)) return null;
    filters.workMode = record.work_mode as WorkModeValue;
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

export function applyMatchFilters(rows: MatchRow[], filters: MatchFilters): MatchRow[] {
  return rows.filter((row) => {
    if (filters.region !== "all" && row.region !== filters.region) return false;
    if (filters.workMode !== "all" && row.workMode !== filters.workMode) return false;
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
    return a.title.localeCompare(b.title);
  });
}