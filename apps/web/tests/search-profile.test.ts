import { beforeEach, describe, expect, it, vi } from "vitest";
import { searchProfileSchema } from "@/lib/search/schema";

const createServerClientMock = vi.hoisted(() => vi.fn());
const createServiceClientMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/server", () => ({
  createClient: createServerClientMock,
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient: createServiceClientMock,
}));

import { POST } from "@/app/api/search-runs/route";

const validSearchProfile = {
  candidate_profile_id: "00000000-0000-4000-8000-000000000001",
  region: "indonesia",
  target_roles: ["Data Engineer"],
  locations: ["Jakarta"],
  work_modes: ["hybrid"],
  employment_types: ["full-time"],
  min_salary: 10_000_000,
  salary_currency: "IDR",
  excluded_keywords: ["sales"],
  daily_enabled: true,
};

function makeRequest(body: unknown): Request {
  return new Request("http://localhost/api/search-runs", {
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
  createServerClientMock.mockResolvedValue({ auth: { getUser } });
  return getUser;
}

describe("searchProfileSchema", () => {
  it("accepts a valid Indonesia search profile", () => {
    expect(searchProfileSchema.safeParse(validSearchProfile).success).toBe(true);
  });

  it("restricts region to Indonesia or Global", () => {
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, region: "asia" }).success).toBe(false);
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, region: "global" }).success).toBe(true);
  });

  it("requires a UUID candidate profile and bounded currency text", () => {
    expect(
      searchProfileSchema.safeParse({
        ...validSearchProfile,
        candidate_profile_id: "profile-1",
      }).success,
    ).toBe(false);
    expect(
      searchProfileSchema.safeParse({
        ...validSearchProfile,
        salary_currency: "X".repeat(33),
      }).success,
    ).toBe(false);
  });

  it("requires at least one nonblank target role", () => {
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, target_roles: [] }).success).toBe(false);
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, target_roles: [" ", ""] }).success).toBe(false);
  });

  it("only accepts supported work modes and employment types", () => {
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, work_modes: ["office"] }).success).toBe(false);
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, employment_types: ["permanent"] }).success).toBe(false);
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, work_modes: ["remote", "on-site"] }).success).toBe(true);
  });

  it("bounds search arrays and individual terms", () => {
    expect(
      searchProfileSchema.safeParse({
        ...validSearchProfile,
        target_roles: Array.from({ length: 21 }, (_, index) => `Role ${index}`),
      }).success,
    ).toBe(false);
    expect(
      searchProfileSchema.safeParse({
        ...validSearchProfile,
        excluded_keywords: ["x".repeat(201)],
      }).success,
    ).toBe(false);
  });

  it("rejects a negative minimum salary", () => {
    expect(searchProfileSchema.safeParse({ ...validSearchProfile, min_salary: -1 }).success).toBe(false);
  });

  it("trims and removes blank array values", () => {
    const result = searchProfileSchema.safeParse({
      ...validSearchProfile,
      target_roles: [" Data Engineer ", " "],
      locations: [" Jakarta ", "", "  Bandung"],
      excluded_keywords: [" sales ", ""],
    });

    expect(result.success).toBe(true);
    if (!result.success) return;
    expect(result.data.target_roles).toEqual(["Data Engineer"]);
    expect(result.data.locations).toEqual(["Jakarta", "Bandung"]);
    expect(result.data.excluded_keywords).toEqual(["sales"]);
  });
});

describe("POST /api/search-runs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.SUPABASE_SERVICE_ROLE_KEY = "service-role-test-key";
  });

  it("rejects an unauthenticated request", async () => {
    const getUser = vi.fn().mockResolvedValue({ data: { user: null }, error: null });
    createServerClientMock.mockResolvedValue({ auth: { getUser } });

    const response = await POST(makeRequest(validSearchProfile));

    expect(response.status).toBe(401);
    expect(createServiceClientMock).not.toHaveBeenCalled();
  });

  it("returns 409 when the profile is not confirmed on the active CV", async () => {
    setupAuthenticatedUser();
    const rpc = vi.fn().mockResolvedValue({
      data: null,
      error: { code: "P0001", message: "confirmed_active_profile_required" },
    });
    createServiceClientMock.mockReturnValue({ rpc });

    const response = await POST(makeRequest(validSearchProfile));

    expect(response.status).toBe(409);
    expect((await response.json()).error).toBe("confirmed_active_profile_required");
  });

  it("returns 202 with the queued run id for a valid request", async () => {
    setupAuthenticatedUser("user-from-cookie");
    const rpc = vi.fn().mockResolvedValue({
      data: [{ search_run_id: "run-1" }],
      error: null,
    });
    createServiceClientMock.mockReturnValue({ rpc });

    const response = await POST(makeRequest(validSearchProfile));

    expect(response.status).toBe(202);
    expect(await response.json()).toEqual({ run_id: "run-1" });
    expect(rpc).toHaveBeenCalledWith(
      "create_manual_search_run",
      expect.objectContaining({
        p_user_id: "user-from-cookie",
        p_candidate_profile_id: "00000000-0000-4000-8000-000000000001",
        p_region: "indonesia",
      }),
    );
  });

  it("rejects an oversized JSON request body", async () => {
    setupAuthenticatedUser();
    const request = makeRequest({
      ...validSearchProfile,
      padding: "x".repeat(70_000),
    });

    const response = await POST(request);

    expect(response.status).toBe(413);
    expect(createServiceClientMock).not.toHaveBeenCalled();
  });

  it("uses the authenticated user instead of a browser-supplied user id", async () => {
    setupAuthenticatedUser("user-from-cookie");
    const rpc = vi.fn().mockResolvedValue({
      data: [{ search_run_id: "run-2" }],
      error: null,
    });
    createServiceClientMock.mockReturnValue({ rpc });

    await POST(makeRequest({ ...validSearchProfile, user_id: "attacker" }));

    const rpcArgs = rpc.mock.calls[0]?.[1] as Record<string, unknown>;
    expect(rpcArgs.p_user_id).toBe("user-from-cookie");
    expect(rpcArgs.user_id).toBeUndefined();
  });
});
