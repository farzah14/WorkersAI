import { beforeEach, describe, expect, it, vi } from "vitest";

const createServerClientMock = vi.hoisted(() => vi.fn());
const createServiceClientMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/supabase/server", () => ({
  createClient: createServerClientMock,
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient: createServiceClientMock,
}));

import { DELETE } from "@/app/api/search-runs/[runId]/route";

const RUN_ID = "00000000-0000-4000-8000-000000000001";

function makeRequest(): Request {
  return new Request(`http://localhost/api/search-runs/${RUN_ID}`, { method: "DELETE" });
}

function makeQuery<T>(result: { data: T; error: unknown | null }) {
  const query = {
    select: vi.fn(() => query),
    eq: vi.fn(() => query),
    not: vi.fn(() => query),
    maybeSingle: vi.fn().mockResolvedValue(result),
    then: (resolve: (value: typeof result) => unknown) => Promise.resolve(result).then(resolve),
  };
  return query;
}

function setupAuthenticatedUser(userId = "user-1") {
  createServerClientMock.mockResolvedValue({
    auth: {
      getUser: vi.fn().mockResolvedValue({ data: { user: { id: userId } }, error: null }),
    },
  });
}

describe("DELETE /api/search-runs/:runId", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("rejects unauthenticated deletion", async () => {
    createServerClientMock.mockResolvedValue({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }) },
    });

    const response = await DELETE(makeRequest(), { params: Promise.resolve({ runId: RUN_ID }) });

    expect(response.status).toBe(401);
    expect(createServiceClientMock).not.toHaveBeenCalled();
  });

  it("deletes a terminal run and its export files for the authenticated owner", async () => {
    setupAuthenticatedUser();
    const runQuery = makeQuery({ data: { status: "partial" }, error: null });
    const exportQuery = makeQuery({ data: [{ storage_path: "user-1/export.xlsx" }], error: null });
    const remove = vi.fn().mockResolvedValue({ error: null });
    const rpc = vi.fn().mockResolvedValue({ data: null, error: null });
    const from = vi.fn((table: string) => (table === "job_search_runs" ? runQuery : exportQuery));
    createServiceClientMock.mockReturnValue({
      from,
      rpc,
      storage: { from: vi.fn(() => ({ remove })) },
    });

    const response = await DELETE(makeRequest(), { params: Promise.resolve({ runId: RUN_ID }) });

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ deleted: true });
    expect(remove).toHaveBeenCalledWith(["user-1/export.xlsx"]);
    expect(rpc).toHaveBeenCalledWith("delete_search_run", {
      p_run_id: RUN_ID,
      p_user_id: "user-1",
    });
  });

  it("does not delete an active run", async () => {
    setupAuthenticatedUser();
    const runQuery = makeQuery({ data: { status: "processing" }, error: null });
    const from = vi.fn(() => runQuery);
    const rpc = vi.fn();
    createServiceClientMock.mockReturnValue({ from, rpc, storage: { from: vi.fn() } });

    const response = await DELETE(makeRequest(), { params: Promise.resolve({ runId: RUN_ID }) });

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({ error: "search_run_active" });
    expect(rpc).not.toHaveBeenCalled();
  });
});
