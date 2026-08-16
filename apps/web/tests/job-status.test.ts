import { beforeEach, describe, expect, it, vi } from "vitest";

const createServerClientMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/server", () => ({
  createClient: createServerClientMock,
}));

import { POST } from "@/app/api/job-status/route";

const JOB_ID = "00000000-0000-4000-8000-000000000001";

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/job-status", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function setupAuthenticatedUser(userId = "auth-user") {
  const getUser = vi.fn().mockResolvedValue({
    data: { user: { id: userId } },
    error: null,
  });
  const upsert = vi.fn().mockResolvedValue({ data: null, error: null });
  const from = vi.fn().mockReturnValue({ upsert });
  createServerClientMock.mockResolvedValue({ auth: { getUser }, from });
  return { getUser, upsert, from };
}

describe("POST /api/job-status", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects an unauthenticated request", async () => {
    createServerClientMock.mockResolvedValue({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }) },
    });

    const response = await POST(makeRequest({ jobId: JOB_ID, status: "saved" }));

    expect(response.status).toBe(401);
  });

  it("rejects an invalid status", async () => {
    setupAuthenticatedUser();

    const response = await POST(makeRequest({ jobId: JOB_ID, status: "deleted" }));

    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("validation_failed");
  });

  it("rejects a malformed job id", async () => {
    setupAuthenticatedUser();

    const response = await POST(makeRequest({ jobId: "not-a-uuid", status: "saved" }));

    expect(response.status).toBe(400);
  });

  it("rejects a malformed body", async () => {
    setupAuthenticatedUser();

    const response = await POST(makeRequest({ jobId: JOB_ID }));

    expect(response.status).toBe(400);
  });

  it("assigns applied_at when marking a job applied", async () => {
    const { upsert } = setupAuthenticatedUser("user-from-cookie");

    const response = await POST(makeRequest({ jobId: JOB_ID, status: "applied" }));

    expect(response.status).toBe(200);
    expect(upsert).toHaveBeenCalledTimes(1);
    const args = upsert.mock.calls[0] as unknown[];
    const payload = args[0] as Record<string, unknown>;
    expect(payload.user_id).toBe("user-from-cookie");
    expect(payload.job_id).toBe(JOB_ID);
    expect(payload.status).toBe("applied");
    expect(typeof payload.applied_at).toBe("string");
  });

  it("clears applied_at when moving from applied to saved", async () => {
    const { upsert } = setupAuthenticatedUser();

    await POST(makeRequest({ jobId: JOB_ID, status: "saved" }));

    const payload = (upsert.mock.calls[0] as unknown[])[0] as Record<string, unknown>;
    expect(payload.status).toBe("saved");
    expect(payload.applied_at).toBeNull();
  });

  it("uses the authenticated user instead of a browser-supplied user id", async () => {
    const { upsert } = setupAuthenticatedUser("user-from-cookie");

    await POST(makeRequest({ jobId: JOB_ID, status: "saved", user_id: "attacker" }));

    const payload = (upsert.mock.calls[0] as unknown[])[0] as Record<string, unknown>;
    expect(payload.user_id).toBe("user-from-cookie");
  });

  it("returns the stored status on success", async () => {
    setupAuthenticatedUser();

    const response = await POST(makeRequest({ jobId: JOB_ID, status: "ignored" }));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ job_id: JOB_ID, status: "ignored" });
  });

  it("returns 500 when the upsert fails", async () => {
    const { upsert } = setupAuthenticatedUser();
    upsert.mockResolvedValue({ data: null, error: { message: "boom" } });

    const response = await POST(makeRequest({ jobId: JOB_ID, status: "saved" }));

    expect(response.status).toBe(500);
  });
});