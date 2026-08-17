import { beforeEach, describe, expect, it, vi } from "vitest";

const createServerClientMock = vi.hoisted(() => vi.fn());
const createServiceClientMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/server", () => ({
  createClient: createServerClientMock,
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient: createServiceClientMock,
}));

import { GET, POST } from "@/app/api/exports/route";

const USER_ID = "00000000-0000-4000-8000-000000000001";
const RUN_ID = "00000000-0000-4000-8000-000000000101";
const EXPORT_ID = "00000000-0000-4000-8000-000000000201";

function makePostRequest(body: unknown): Request {
  return new Request("http://localhost/api/exports", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function setupAuthenticatedUser(userId = USER_ID) {
  const getUser = vi.fn().mockResolvedValue({
    data: { user: { id: userId } },
    error: null,
  });
  const runChain = {
    select: vi.fn().mockReturnValue({
      eq: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          maybeSingle: vi.fn().mockResolvedValue({ data: { id: RUN_ID }, error: null }),
        }),
      }),
    }),
  };
  const createSignedUrl = vi
    .fn()
    .mockResolvedValue({ data: { signedUrl: "https://example.test/signed/report.xlsx" }, error: null });
  createServerClientMock.mockResolvedValue({
    auth: { getUser },
    from: vi.fn((table: string) =>
      table === "job_search_runs" ? runChain : { insert: vi.fn(), select: vi.fn() },
    ),
    storage: { from: vi.fn(() => ({ createSignedUrl })) },
  });
  return { getUser, runChain, createSignedUrl };
}

describe("POST /api/exports", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.SUPABASE_SERVICE_ROLE_KEY = "service-role-key";
  });

  it("rejects an unauthenticated request", async () => {
    createServerClientMock.mockResolvedValue({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }) },
    });

    const response = await POST(
      makePostRequest({ searchRunId: RUN_ID, format: "xlsx", scope: "all" }),
    );

    expect(response.status).toBe(401);
  });

  it("rejects a malformed body", async () => {
    setupAuthenticatedUser();

    const response = await POST(
      new Request("http://localhost/api/exports", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{not json",
      }),
    );

    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("validation_failed");
  });

  it("rejects an unsupported format", async () => {
    setupAuthenticatedUser();

    const response = await POST(
      makePostRequest({ searchRunId: RUN_ID, format: "csv", scope: "all" }),
    );

    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("validation_failed");
  });

  it("rejects an unknown scope", async () => {
    setupAuthenticatedUser();

    const response = await POST(
      makePostRequest({ searchRunId: RUN_ID, format: "xlsx", scope: "everything" }),
    );

    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("validation_failed");
  });

  it("rejects filters with arbitrary fields", async () => {
    setupAuthenticatedUser();

    const response = await POST(
      makePostRequest({
        searchRunId: RUN_ID,
        format: "xlsx",
        scope: "current_filters",
        filters: { sql_field: "1 = 1" },
      }),
    );

    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("validation_failed");
  });

  it("rejects filters with invalid value types", async () => {
    setupAuthenticatedUser();

    const response = await POST(
      makePostRequest({
        searchRunId: RUN_ID,
        format: "pdf",
        scope: "current_filters",
        filters: { min_score: "ninety" },
      }),
    );

    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe("validation_failed");
  });

  it("rejects a search run the user does not own", async () => {
    const { runChain } = setupAuthenticatedUser();
    const maybeSingle = vi.fn().mockResolvedValue({ data: null, error: null });
    runChain.select.mockReturnValue({
      eq: vi.fn().mockReturnValue({ eq: vi.fn().mockReturnValue({ maybeSingle }) }),
    });

    const response = await POST(
      makePostRequest({ searchRunId: RUN_ID, format: "xlsx", scope: "all" }),
    );

    expect(response.status).toBe(404);
    expect((await response.json()).error).toBe("run_not_found");
  });

  it("creates the export row and enqueues generation", async () => {
    setupAuthenticatedUser();

    const exportsInsert = vi.fn().mockReturnValue({
      select: vi.fn().mockReturnValue({
        single: vi.fn().mockResolvedValue({ data: { id: EXPORT_ID }, error: null }),
      }),
    });
    const exportsChain = { insert: exportsInsert };
    createServerClientMock.mockResolvedValue({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: { id: USER_ID } }, error: null }) },
      from: vi.fn((table: string) => {
        if (table === "job_search_runs") {
          return {
            select: vi.fn().mockReturnValue({
              eq: vi.fn().mockReturnValue({
                eq: vi.fn().mockReturnValue({
                  maybeSingle: vi.fn().mockResolvedValue({ data: { id: RUN_ID }, error: null }),
                }),
              }),
            }),
          };
        }
        return exportsChain;
      }),
    });
    const workItemsInsert = vi.fn().mockResolvedValue({ data: null, error: null });
    createServiceClientMock.mockReturnValue({
      from: vi.fn().mockReturnValue({ insert: workItemsInsert }),
    });

    const response = await POST(
      makePostRequest({
        searchRunId: RUN_ID,
        format: "xlsx",
        scope: "current_filters",
        filters: { min_score: 80, status: ["saved"] },
      }),
    );

    expect(response.status).toBe(202);
    expect((await response.json()).id).toBe(EXPORT_ID);
    expect(exportsInsert).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: USER_ID,
        search_run_id: RUN_ID,
        format: "xlsx",
        scope: "current_filters",
        status: "queued",
      }),
    );
    expect(workItemsInsert).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "generate_export",
        dedupe_key: `generate_export:${EXPORT_ID}`,
        payload: expect.objectContaining({ export_id: EXPORT_ID, user_id: USER_ID }),
      }),
    );
  });
});

describe("GET /api/exports", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects an unauthenticated request", async () => {
    createServerClientMock.mockResolvedValue({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }) },
    });

    const response = await GET();

    expect(response.status).toBe(401);
  });

  it("lists owned exports without signed urls for queued rows", async () => {
    const { createSignedUrl } = setupAuthenticatedUser();

    const rows = [
      {
        id: EXPORT_ID,
        user_id: USER_ID,
        search_run_id: RUN_ID,
        format: "xlsx",
        scope: "all",
        filter_json: {},
        status: "queued",
        storage_path: null,
        error_code: null,
        created_at: "2026-08-17T01:00:00Z",
        completed_at: null,
      },
    ];
    const exportsChain = {
      insert: vi.fn(),
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          order: vi.fn().mockResolvedValue({ data: rows, error: null }),
        }),
      }),
    };
    createServerClientMock.mockResolvedValue({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: { id: USER_ID } }, error: null }) },
      from: vi.fn(() => exportsChain),
      storage: { from: vi.fn(() => ({ createSignedUrl })) },
    });

    const response = await GET();

    expect(response.status).toBe(200);
    const body = (await response.json()) as { exports: Array<{ id: string; download_url: string | null }> };
    expect(body.exports).toHaveLength(1);
    expect(body.exports[0].id).toBe(EXPORT_ID);
    expect(body.exports[0].download_url).toBeNull();
    expect(createSignedUrl).not.toHaveBeenCalled();
  });

  it("creates a short-lived signed url only for completed rows", async () => {
    const { createSignedUrl } = setupAuthenticatedUser();

    const rows = [
      {
        id: EXPORT_ID,
        user_id: USER_ID,
        search_run_id: RUN_ID,
        format: "pdf",
        scope: "best_and_strong",
        filter_json: {},
        status: "completed",
        storage_path: `${USER_ID}/${EXPORT_ID}/report.pdf`,
        error_code: null,
        created_at: "2026-08-17T01:00:00Z",
        completed_at: "2026-08-17T01:05:00Z",
      },
      {
        id: "00000000-0000-4000-8000-000000000202",
        user_id: USER_ID,
        search_run_id: RUN_ID,
        format: "xlsx",
        scope: "all",
        filter_json: {},
        status: "failed",
        storage_path: null,
        error_code: "generate_failed",
        created_at: "2026-08-17T02:00:00Z",
        completed_at: null,
      },
    ];
    const exportsChain = {
      insert: vi.fn(),
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          order: vi.fn().mockResolvedValue({ data: rows, error: null }),
        }),
      }),
    };
    createServerClientMock.mockResolvedValue({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: { id: USER_ID } }, error: null }) },
      from: vi.fn(() => exportsChain),
      storage: { from: vi.fn(() => ({ createSignedUrl })) },
    });

    const response = await GET();

    expect(response.status).toBe(200);
    const body = (await response.json()) as { exports: Array<{ id: string; download_url: string | null }> };
    expect(body.exports[0].download_url).toBe("https://example.test/signed/report.xlsx");
    expect(body.exports[1].download_url).toBeNull();
    expect(createSignedUrl).toHaveBeenCalledTimes(1);
    expect(createSignedUrl).toHaveBeenCalledWith(`${USER_ID}/${EXPORT_ID}/report.pdf`, 3600);
  });
});