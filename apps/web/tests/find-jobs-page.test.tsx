import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const pushMock = vi.hoisted(() => vi.fn());
const createClientMock = vi.hoisted(() => vi.fn());
const getUserMock = vi.hoisted(() => vi.fn());
const cvMaybeSingleMock = vi.hoisted(() => vi.fn());
const profileMaybeSingleMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: createClientMock,
}));

import FindJobsPage from "@/app/find-jobs/page";

function makeQuery(maybeSingle: ReturnType<typeof vi.fn>) {
  return {
    select: vi.fn().mockReturnThis(),
    eq: vi.fn().mockReturnThis(),
    not: vi.fn().mockReturnThis(),
    order: vi.fn().mockReturnThis(),
    limit: vi.fn().mockReturnThis(),
    maybeSingle,
  };
}

function setupSearchProfile(): void {
  getUserMock.mockResolvedValue({
    data: { user: { id: "user-1" } },
    error: null,
  });
  cvMaybeSingleMock.mockResolvedValue({
    data: { id: "cv-1", original_name: "candidate.pdf" },
    error: null,
  });
  profileMaybeSingleMock.mockResolvedValue({
    data: {
      id: "00000000-0000-4000-8000-000000000001",
      profile: {
        name: "Candidate",
        current_role: "Data Engineer",
        seniority: "mid",
        target_roles: ["Data Engineer"],
        skills: ["SQL", "Python"],
        experience_years: 4,
        languages: ["English"],
        education: ["Bachelor"],
      },
      version: 1,
      confirmed_at: "2026-09-12T00:00:00.000Z",
    },
    error: null,
  });

  const cvQuery = makeQuery(cvMaybeSingleMock);
  const profileQuery = makeQuery(profileMaybeSingleMock);
  createClientMock.mockReturnValue({
    auth: { getUser: getUserMock },
    from: vi.fn((table: string) => (table === "cvs" ? cvQuery : profileQuery)),
  });
}

async function renderReadyPage(): Promise<void> {
  render(<FindJobsPage />);
  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Find Jobs Now" })).toBeEnabled();
  });
}

describe("FindJobsPage search navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupSearchProfile();
    global.fetch = vi.fn();
  });

  it("navigates to the dashboard after an accepted search run", async () => {
    await renderReadyPage();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({ run_id: "run-1" }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Find Jobs Now" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
    expect(screen.queryByText(/Search queued/)).not.toBeInTheDocument();
  });

  it("keeps a rejected search on the find-jobs page", async () => {
    await renderReadyPage();
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ error: "quota_exceeded" }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Find Jobs Now" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("quota_exceeded"));
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("shows an error when an accepted response has no run id", async () => {
    await renderReadyPage();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({}),
    });

    fireEvent.click(screen.getByRole("button", { name: "Find Jobs Now" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not start the job search."));
    expect(pushMock).not.toHaveBeenCalled();
  });
});
