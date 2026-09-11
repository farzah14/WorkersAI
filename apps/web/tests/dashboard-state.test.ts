import { describe, expect, it } from "vitest";
import {
  dashboardEmptyState,
  dashboardEmptyMessageKey,
  processingMessageKey,
  showIndonesiaCoverageNotice,
} from "@/lib/jobs/dashboard-state";

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

describe("dashboardEmptyMessageKey", () => {
  it("explains strict verification when an Indonesia run has zero matches", () => {
    expect(dashboardEmptyMessageKey("completed", 0, "indonesia")).toBe(
      "dashboard.indonesiaNoVerifiedJobs",
    );
    expect(dashboardEmptyMessageKey("partial", 0, "indonesia")).toBe(
      "dashboard.indonesiaNoVerifiedJobs",
    );
  });

  it("preserves processing, failure, and global empty messages", () => {
    expect(dashboardEmptyMessageKey("processing", 0, "indonesia")).toBe(
      "dashboard.processingHint",
    );
    expect(dashboardEmptyMessageKey("failed", 0, "indonesia")).toBe(
      "dashboard.failedHint",
    );
    expect(dashboardEmptyMessageKey("completed", 0, "global")).toBe(
      "dashboard.noMatchesHint",
    );
  });
});

describe("showIndonesiaCoverageNotice", () => {
  it("shows only for one to four terminal Indonesia results", () => {
    expect(showIndonesiaCoverageNotice("completed", 1, "indonesia")).toBe(true);
    expect(showIndonesiaCoverageNotice("partial", 4, "indonesia")).toBe(true);
    expect(showIndonesiaCoverageNotice("processing", 4, "indonesia")).toBe(false);
    expect(showIndonesiaCoverageNotice("completed", 0, "indonesia")).toBe(false);
    expect(showIndonesiaCoverageNotice("completed", 5, "indonesia")).toBe(false);
    expect(showIndonesiaCoverageNotice("completed", 3, "global")).toBe(false);
  });
});
