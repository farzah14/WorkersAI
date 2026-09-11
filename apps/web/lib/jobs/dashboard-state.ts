export type SearchRunStatus = "queued" | "processing" | "completed" | "partial" | "failed";
export type DashboardEmptyState = "processing" | "empty" | "matches";

export function dashboardEmptyState(
  status: SearchRunStatus,
  matchCount: number,
): DashboardEmptyState {
  if (matchCount > 0) return "matches";
  if (status === "queued" || status === "processing") return "processing";
  return "empty";
}

export function processingMessageKey(status: SearchRunStatus): string {
  return `processing.${status === "processing" ? "running" : status}`;
}

export function dashboardEmptyMessageKey(
  status: SearchRunStatus,
  matchCount: number,
  region: string,
): string {
  if (status === "queued" || status === "processing") {
    return "dashboard.processingHint";
  }
  if (status === "failed") return "dashboard.failedHint";
  if (matchCount === 0 && region === "indonesia") {
    return "dashboard.indonesiaNoVerifiedJobs";
  }
  return "dashboard.noMatchesHint";
}

export function showIndonesiaCoverageNotice(
  status: SearchRunStatus,
  matchCount: number,
  region: string,
): boolean {
  return (
    region === "indonesia" &&
    (status === "completed" || status === "partial") &&
    matchCount > 0 &&
    matchCount < 5
  );
}
