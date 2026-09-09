import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const refreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock }),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const messages: Record<string, string> = {
      createXlsx: "Export Excel (.xlsx)",
      createPdf: "Export PDF (.pdf)",
      creating: "Requesting export…",
      requestAccepted: "Export request accepted. Processing in background.",
      requestFailed: "Could not create export request. Please try again.",
    };
    return messages[key] ?? key;
  },
}));

import { ExportRequestForm } from "@/components/export-request-form";

describe("ExportRequestForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it("submits Excel format export request and displays success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({ id: "export-1" }),
    });
    global.fetch = fetchMock;

    render(<ExportRequestForm runId="run-1" />);

    const xlsxButton = screen.getByRole("button", { name: "Export Excel (.xlsx)" });
    fireEvent.click(xlsxButton);

    expect(xlsxButton).toBeDisabled();

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/exports", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          searchRunId: "run-1",
          format: "xlsx",
          scope: "all",
          filters: undefined,
        }),
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Export request accepted. Processing in background.")).toBeDefined();
    });
    expect(refreshMock).toHaveBeenCalled();
  });

  it("submits PDF format export request with current filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({ id: "export-2" }),
    });
    global.fetch = fetchMock;

    const filters = {
      region: ["indonesia"],
      work_mode: ["remote"],
      min_score: 80,
    };

    render(<ExportRequestForm runId="run-1" filters={filters} />);

    const pdfButton = screen.getByRole("button", { name: "Export PDF (.pdf)" });
    fireEvent.click(pdfButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/exports", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          searchRunId: "run-1",
          format: "pdf",
          scope: "current_filters",
          filters,
        }),
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Export request accepted. Processing in background.")).toBeDefined();
    });
  });

  it("displays error message when export request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: "export_create_failed" }),
    });
    global.fetch = fetchMock;

    render(<ExportRequestForm runId="run-1" />);

    const xlsxButton = screen.getByRole("button", { name: "Export Excel (.xlsx)" });
    fireEvent.click(xlsxButton);

    await waitFor(() => {
      expect(screen.getByText("Could not create export request. Please try again.")).toBeDefined();
    });
    expect(xlsxButton).not.toBeDisabled();
  });
});
