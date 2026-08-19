import { beforeEach, describe, expect, it, vi } from "vitest";
import { DELETE as deleteCv } from "@/app/api/cvs/route";
import { DELETE as deleteAccount } from "@/app/api/account/delete/route";
import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";

vi.mock("@/lib/supabase/server", () => ({
  createClient: vi.fn(),
}));
vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(),
}));

const createServerClientMock = vi.mocked(createServerClient);
const createServiceClientMock = vi.mocked(createServiceClient);

const USER_ID = "user-1";
const OTHER_USER_ID = "user-2";
const CV_ID = "11111111-1111-1111-1111-111111111111";
const CV_PATH = `${USER_ID}/${CV_ID}/resume.pdf`;

function authenticatedUser(userId = USER_ID) {
  return {
    data: { user: { id: userId } },
    error: null,
  };
}

function authOnly(client: unknown) {
  createServerClientMock.mockResolvedValue(client as never);
}

function storageClient(removals: Array<{ bucket: string; paths: string[] }>) {
  return {
    storage: {
      from: vi.fn((bucket: string) => ({
        remove: vi.fn(async (paths: string[]) => {
          removals.push({ bucket, paths });
          return { data: [], error: null };
        }),
      })),
    },
  };
}

function cvChain(cvResult: unknown) {
  return {
    select: vi.fn().mockReturnValue({
      eq: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          maybeSingle: vi.fn().mockResolvedValue(cvResult),
        }),
      }),
    }),
    update: vi.fn().mockReturnValue({
      eq: vi.fn().mockReturnValue({
        eq: vi.fn().mockResolvedValue({ data: null, error: null }),
      }),
    }),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DELETE /api/cvs (delete original file, keep profile)", () => {
  function makeRequest(cvId: string | null): Request {
    const url = new URL("http://localhost/api/cvs");
    if (cvId) url.searchParams.set("cv_id", cvId);
    return new Request(url, { method: "DELETE" });
  }

  it("removes the private object and keeps the structured profile", async () => {
    authOnly({
      auth: { getUser: vi.fn().mockResolvedValue(authenticatedUser()) },
      from: vi.fn((table: string) => {
        if (table === "cvs") {
          return cvChain({ data: { id: CV_ID, storage_path: CV_PATH }, error: null });
        }
        throw new Error(`unexpected table ${table}`);
      }),
    });
    const removals: Array<{ bucket: string; paths: string[] }> = [];
    createServiceClientMock.mockReturnValue(storageClient(removals) as never);

    const response = await deleteCv(makeRequest(CV_ID));

    expect(response.status).toBe(200);
    expect(removals).toEqual([{ bucket: "cvs", paths: [CV_PATH] }]);
  });

  it("returns 404 for a cv owned by another user", async () => {
    authOnly({
      auth: { getUser: vi.fn().mockResolvedValue(authenticatedUser()) },
      from: vi.fn((table: string) => {
        if (table === "cvs") {
          return cvChain({ data: null, error: null });
        }
        throw new Error(`unexpected table ${table}`);
      }),
    });
    createServiceClientMock.mockReturnValue(storageClient([]) as never);

    const response = await deleteCv(makeRequest(CV_ID));

    expect(response.status).toBe(404);
  });

  it("returns 400 for a missing or malformed cv id", async () => {
    authOnly({
      auth: { getUser: vi.fn().mockResolvedValue(authenticatedUser()) },
    });
    createServiceClientMock.mockReturnValue(storageClient([]) as never);

    expect((await deleteCv(makeRequest(null))).status).toBe(400);
    expect((await deleteCv(makeRequest("not-a-uuid"))).status).toBe(400);
  });

  it("treats an already-missing object as idempotent success", async () => {
    authOnly({
      auth: { getUser: vi.fn().mockResolvedValue(authenticatedUser()) },
      from: vi.fn((table: string) => {
        if (table === "cvs") {
          return cvChain({ data: { id: CV_ID, storage_path: CV_PATH }, error: null });
        }
        throw new Error(`unexpected table ${table}`);
      }),
    });
    createServiceClientMock.mockReturnValue({
      storage: {
        from: vi.fn(() => ({
          remove: vi.fn().mockResolvedValue({
            data: null,
            error: { message: "The resource was not found" },
          }),
        })),
      },
    } as never);

    const response = await deleteCv(makeRequest(CV_ID));

    expect(response.status).toBe(200);
  });

  it("returns 401 without a session", async () => {
    authOnly({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }) },
    });

    expect((await deleteCv(makeRequest(CV_ID))).status).toBe(401);
  });
});

describe("DELETE /api/account/delete", () => {
  function makeRequest(confirmation: string, bodyUserId?: string): Request {
    return new Request("http://localhost/api/account/delete", {
      method: "DELETE",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ confirmation, user_id: bodyUserId }),
    });
  }

  function makeClient({ cvs = [CV_PATH], exports: exportPaths = [] }: { cvs?: string[]; exports?: string[] }) {
    return {
      auth: {
        getUser: vi.fn().mockResolvedValue(authenticatedUser()),
      },
      from: vi.fn((table: string) => {
        const paths = table === "cvs" ? cvs : exportPaths;
        return {
          select: vi.fn().mockReturnValue({
            eq: vi.fn().mockReturnValue({
              not: vi.fn().mockReturnValue({
                then: (resolve: (value: unknown) => void) => {
                  resolve({
                    data: paths.map((p) => ({ storage_path: p })),
                    error: null,
                  });
                },
              }),
            }),
          }),
        };
      }),
    };
  }

  function accountServiceClient(
    removals: Array<{ bucket: string; paths: string[] }>,
    deleteUserError: unknown = null,
    rpcError: unknown = null,
  ) {
    return {
      storage: {
        from: vi.fn((bucket: string) => ({
          remove: vi.fn(async (paths: string[]) => {
            removals.push({ bucket, paths });
            return { data: [], error: null };
          }),
        })),
      },
      rpc: vi.fn().mockResolvedValue({ data: null, error: rpcError }),
      auth: {
        admin: {
          deleteUser: vi.fn().mockResolvedValue({ data: null, error: deleteUserError }),
        },
      },
    };
  }

  it("removes cv and export objects before deleting the auth user", async () => {
    authOnly(makeClient({ cvs: [CV_PATH], exports: [`${USER_ID}/exp-1/report.xlsx`] }));
    const removals: Array<{ bucket: string; paths: string[] }> = [];
    createServiceClientMock.mockReturnValue(accountServiceClient(removals) as never);

    const response = await deleteAccount(makeRequest("DELETE", OTHER_USER_ID));

    expect(response.status).toBe(200);
    expect(removals).toEqual([
      { bucket: "cvs", paths: [CV_PATH] },
      { bucket: "exports", paths: [`${USER_ID}/exp-1/report.xlsx`] },
    ]);
  });

  it("purges the user's queued work items before deleting the auth user", async () => {
    authOnly(makeClient({}));
    const calls: string[] = [];
    const serviceClient = accountServiceClient([]);
    vi.mocked(serviceClient.rpc).mockImplementation(async (fn: string) => {
      calls.push(fn);
      return { data: null, error: null };
    });
    vi.mocked(serviceClient.auth.admin.deleteUser).mockImplementation(async () => {
      calls.push("deleteUser");
      return { data: null, error: null };
    });
    createServiceClientMock.mockReturnValue(serviceClient as never);

    const response = await deleteAccount(makeRequest("DELETE"));

    expect(response.status).toBe(200);
    expect(serviceClient.rpc).toHaveBeenCalledWith("delete_account_cleanup", {
      p_user_id: USER_ID,
    });
    expect(calls).toEqual(["delete_account_cleanup", "deleteUser"]);
  });

  it("does not delete the user when work item cleanup fails", async () => {
    authOnly(makeClient({}));
    const deleteUser = vi.fn();
    createServiceClientMock.mockReturnValue({
      storage: {
        from: vi.fn(() => ({
          remove: vi.fn().mockResolvedValue({ data: [], error: null }),
        })),
      },
      rpc: vi.fn().mockResolvedValue({ data: null, error: { message: "rpc down" } }),
      auth: { admin: { deleteUser } },
    } as never);

    const response = await deleteAccount(makeRequest("DELETE"));

    expect(response.status).toBe(500);
    expect(deleteUser).not.toHaveBeenCalled();
  });

  it("requires the DELETE confirmation token", async () => {
    authOnly(makeClient({}));
    createServiceClientMock.mockReturnValue(accountServiceClient([]) as never);

    const response = await deleteAccount(makeRequest("CONFIRM"));

    expect(response.status).toBe(400);
  });

  it("returns 401 without a session", async () => {
    authOnly({
      auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }) },
    });

    expect((await deleteAccount(makeRequest("DELETE"))).status).toBe(401);
  });

  it("does not delete the user when storage cleanup fails", async () => {
    authOnly(makeClient({ cvs: [CV_PATH] }));
    const deleteUser = vi.fn();
    createServiceClientMock.mockReturnValue({
      storage: {
        from: vi.fn(() => ({
          remove: vi.fn().mockResolvedValue({
            data: null,
            error: { message: "storage is down" },
          }),
        })),
      },
      auth: { admin: { deleteUser } },
    } as never);

    const response = await deleteAccount(makeRequest("DELETE"));

    expect(response.status).toBe(500);
    expect(deleteUser).not.toHaveBeenCalled();
  });

  it("returns 500 when the auth user deletion fails", async () => {
    authOnly(makeClient({ cvs: [], exports: [] }));
    createServiceClientMock.mockReturnValue(
      accountServiceClient([], { message: "boom" }) as never,
    );

    const response = await deleteAccount(makeRequest("DELETE"));

    expect(response.status).toBe(500);
  });
});