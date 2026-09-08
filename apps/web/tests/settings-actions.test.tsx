import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const refreshMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock }),
}));

import { SettingsActions } from "@/app/settings/settings-actions";

const copy = {
  deleteOriginal: "Delete",
  confirmationLabel: "Type DELETE to confirm",
  deleteAccount: "Delete my account",
  accountDeleted: "Account deleted.",
  invalidConfirmation: "Type DELETE to confirm.",
  error: "Could not complete the request.",
};

describe("SettingsActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
  });

  it("requests full CV deletion from the CV settings action", async () => {
    render(
      <SettingsActions
        cv={{ id: "cv-1", original_name: "synthetic.pdf" }}
        copy={copy}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const [input, init] = vi.mocked(global.fetch).mock.calls[0];
    const url = new URL(String(input), window.location.origin);
    expect(url.pathname).toBe("/api/cvs");
    expect(url.searchParams.get("cv_id")).toBe("cv-1");
    expect(url.searchParams.get("mode")).toBe("full");
    expect(init?.method).toBe("DELETE");
  });

  it("refreshes after a successful full deletion", async () => {
    render(
      <SettingsActions
        cv={{ id: "cv-1", original_name: "synthetic.pdf" }}
        copy={copy}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(refreshMock).toHaveBeenCalledTimes(1));
  });

  it("shows a sanitized error and re-enables the action when deletion fails", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(
      <SettingsActions
        cv={{ id: "cv-1", original_name: "synthetic.pdf" }}
        copy={copy}
      />,
    );

    const button = screen.getByRole("button", { name: "Delete" });
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByText(copy.error)).toBeInTheDocument());
    expect(button).not.toBeDisabled();
    expect(refreshMock).not.toHaveBeenCalled();
  });
});
