import { describe, expect, it } from "vitest";
import { dashboardEmptyState, processingMessageKey } from "@/lib/jobs/dashboard-state";

describe("dashboardEmptyState", () => {
  it("reports an active newest run as processing instead of no results", () => {
    expect(dashboardEmptyState("queued", 0)).toBe("processing");
    expect(dashboardEmptyState("processing", 0)).toBe("processing");
  });

  it("reports a terminal run with no matches as empty", () => {
    expect(dashboardEmptyState("completed", 0)).toBe("empty");
    expect(dashboardEmptyState("partial", 0)).toBe("empty");
    expect(dashboardEmptyState("failed", 0)).toBe("empty");
  });

  it("does not replace existing matches with a status message", () => {
    expect(dashboardEmptyState("processing", 1)).toBe("matches");
  });
});

describe("processingMessageKey", () => {
  it("maps the processing run status to the existing running translation", () => {
    expect(processingMessageKey("processing")).toBe("processing.running");
    expect(processingMessageKey("queued")).toBe("processing.queued");
    expect(processingMessageKey("completed")).toBe("processing.completed");
    expect(processingMessageKey("partial")).toBe("processing.partial");
    expect(processingMessageKey("failed")).toBe("processing.failed");
  });
});
