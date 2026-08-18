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
