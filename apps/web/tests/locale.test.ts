import { beforeEach, describe, expect, it, vi } from "vitest";

const createServerClientMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/server", () => ({
  createClient: createServerClientMock,
}));

import { POST } from "@/app/api/locale/route";

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/locale", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function setupAuthenticatedUser(userId = "00000000-0000-4000-8000-000000000001") {
  const getUser = vi.fn().mockResolvedValue({
    data: { user: { id: userId } },
    error: null,
  });
  const eq = vi.fn().mockResolvedValue({ data: null, error: null });
  const update = vi.fn().mockReturnValue({ eq });
  const from = vi.fn().mockReturnValue({ update });
  createServerClientMock.mockResolvedValue({ auth: { getUser }, from });
  return { getUser, update, eq, from };
}

describe("POST /api/locale", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects an unauthenticated request", async () => {
    createServerClientMock.mockResolvedValue({
      auth: {
        getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: new Error("no session") }),
      },
    });

    const response = await POST(makeRequest({ locale: "en" }));
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: "unauthorized" });
  });

  it("rejects invalid json", async () => {
    setupAuthenticatedUser();
    const req = new Request("http://localhost/api/locale", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "invalid-json{",
    });

    const response = await POST(req);
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "invalid_json" });
  });

  it("rejects unsupported locale", async () => {
    setupAuthenticatedUser();
    const response = await POST(makeRequest({ locale: "fr" }));
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "validation_failed" });
  });

  it("updates public.profiles matching by user_id column", async () => {
    const userId = "00000000-0000-4000-8000-000000000001";
    const { from, update, eq } = setupAuthenticatedUser(userId);

    const response = await POST(makeRequest({ locale: "en" }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ locale: "en" });

    expect(from).toHaveBeenCalledWith("profiles");
    expect(update).toHaveBeenCalledWith({ locale: "en" });
    expect(eq).toHaveBeenCalledWith("user_id", userId);
  });

  it("returns 500 when update fails", async () => {
    const userId = "00000000-0000-4000-8000-000000000001";
    const getUser = vi.fn().mockResolvedValue({
      data: { user: { id: userId } },
      error: null,
    });
    const eq = vi.fn().mockResolvedValue({ error: { message: "db error" } });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    createServerClientMock.mockResolvedValue({ auth: { getUser }, from });

    const response = await POST(makeRequest({ locale: "id" }));
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error: "locale_update_failed" });
  });
});
