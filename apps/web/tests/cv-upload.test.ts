import { beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/cvs/route";
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
const CV_ID = "11111111-1111-1111-1111-111111111111";
const CV_PATH = `${USER_ID}/${CV_ID}/Resume_Final.pdf`;

function makeRequest() {
  const formData = new FormData();
  formData.set(
    "file",
    new File(["digital cv"], "Resume Final.pdf", { type: "application/pdf" }),
  );
  return {
    formData: vi.fn().mockResolvedValue(formData),
  };
}

function makeUploadClient(pathError: unknown) {
  const deleteEq = vi.fn().mockResolvedValue({ data: null, error: null });
  const remove = vi.fn().mockResolvedValue({ data: [], error: null });
  const upload = vi.fn().mockResolvedValue({ data: { path: CV_PATH }, error: null });
  const update = vi.fn().mockReturnValue({
    eq: vi.fn().mockResolvedValue({ data: null, error: pathError }),
  });

  return {
    client: {
      auth: {
        getUser: vi.fn().mockResolvedValue({
          data: { user: { id: USER_ID } },
          error: null,
        }),
      },
      rpc: vi.fn().mockResolvedValue({ data: 1, error: null }),
      from: vi.fn((table: string) => {
        if (table !== "cvs") throw new Error(`unexpected table ${table}`);
        return {
          insert: vi.fn().mockReturnValue({
            select: vi.fn().mockReturnValue({
              single: vi.fn().mockResolvedValue({ data: { id: CV_ID }, error: null }),
            }),
          }),
          update,
          delete: vi.fn().mockReturnValue({ eq: deleteEq }),
        };
      }),
      storage: {
        from: vi.fn((bucket: string) => {
          if (bucket !== "cvs") throw new Error(`unexpected bucket ${bucket}`);
          return { upload, remove };
        }),
      },
    },
    deleteEq,
    update,
  };
}

function makeServiceClient({
  queueError = null,
  removeError = null,
  rpcError = null,
  removeReject,
  rpcReject,
}: {
  queueError?: unknown;
  removeError?: unknown;
  rpcError?: unknown;
  removeReject?: unknown;
  rpcReject?: unknown;
} = {}) {
  const remove = removeReject
    ? vi.fn().mockRejectedValue(removeReject)
    : vi.fn().mockResolvedValue({ data: [], error: removeError });
  const rpc = rpcReject
    ? vi.fn().mockRejectedValue(rpcReject)
    : vi.fn().mockResolvedValue({ data: null, error: rpcError });
  const referenceUserEq = vi.fn().mockResolvedValue({ data: null, error: null });
  const referenceIdEq = vi.fn().mockReturnValue({ eq: referenceUserEq });
  const referenceUpdate = vi.fn().mockReturnValue({ eq: referenceIdEq });

  return {
    client: {
      from: vi.fn((table: string) => {
        if (table === "work_items") {
          return {
            insert: vi.fn().mockResolvedValue({ data: null, error: queueError }),
          };
        }
        if (table === "cvs") return { update: referenceUpdate };
        throw new Error(`unexpected table ${table}`);
      }),
      storage: {
        from: vi.fn((bucket: string) => {
          if (bucket !== "cvs") throw new Error(`unexpected bucket ${bucket}`);
          return { remove };
        }),
      },
      rpc,
    },
    remove,
    rpc,
    referenceIdEq,
    referenceUpdate,
    referenceUserEq,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("POST /api/cvs cleanup after storage upload", () => {
  it("removes the exact object and provisional row when storage-path persistence fails", async () => {
    const { client } = makeUploadClient({ message: "database unavailable" });
    const {
      client: serviceClient,
      remove,
      rpc,
      referenceIdEq,
      referenceUpdate,
      referenceUserEq,
    } = makeServiceClient();
    createServerClientMock.mockResolvedValue(client as never);
    createServiceClientMock.mockReturnValue(serviceClient as never);

    const response = await POST(makeRequest() as never);

    expect(response.status).toBe(500);
    expect(referenceUpdate).toHaveBeenCalledWith({ storage_path: CV_PATH });
    expect(referenceIdEq).toHaveBeenCalledWith("id", CV_ID);
    expect(referenceUserEq).toHaveBeenCalledWith("user_id", USER_ID);
    expect(remove).toHaveBeenCalledWith([CV_PATH]);
    expect(rpc).toHaveBeenCalledWith("delete_cv", {
      p_cv_id: CV_ID,
      p_user_id: USER_ID,
    });
  });

  it("removes the exact object and provisional row when queue insertion fails", async () => {
    const { client } = makeUploadClient(null);
    const {
      client: serviceClient,
      remove,
      rpc,
    } = makeServiceClient({ queueError: { message: "queue unavailable" } });
    createServerClientMock.mockResolvedValue(client as never);
    createServiceClientMock.mockReturnValue(serviceClient as never);

    const response = await POST(makeRequest() as never);

    expect(response.status).toBe(500);
    expect(remove).toHaveBeenCalledWith([CV_PATH]);
    expect(rpc).toHaveBeenCalledWith("delete_cv", {
      p_cv_id: CV_ID,
      p_user_id: USER_ID,
    });
  });

  it("retains the durable CV row when storage removal resolves with an error", async () => {
    const { client, deleteEq, update } = makeUploadClient(null);
    const { client: serviceClient, remove, rpc } = makeServiceClient({
      queueError: { message: "queue unavailable" },
      removeError: { message: "storage unavailable" },
    });
    createServerClientMock.mockResolvedValue(client as never);
    createServiceClientMock.mockReturnValue(serviceClient as never);

    const response = await POST(makeRequest() as never);

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "could not enqueue cv extraction",
      cleanup: "incomplete",
    });
    expect(update).toHaveBeenCalledWith({ storage_path: CV_PATH });
    expect(remove).toHaveBeenCalledWith([CV_PATH]);
    expect(rpc).not.toHaveBeenCalled();
    expect(deleteEq).not.toHaveBeenCalled();
  });

  it("reports incomplete cleanup when delete_cv resolves with an error", async () => {
    const { client } = makeUploadClient(null);
    const { client: serviceClient, remove, rpc } = makeServiceClient({
      queueError: { message: "queue unavailable" },
      rpcError: { message: "database unavailable" },
    });
    createServerClientMock.mockResolvedValue(client as never);
    createServiceClientMock.mockReturnValue(serviceClient as never);

    const response = await POST(makeRequest() as never);

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "could not enqueue cv extraction",
      cleanup: "incomplete",
    });
    expect(remove).toHaveBeenCalledWith([CV_PATH]);
    expect(rpc).toHaveBeenCalledWith("delete_cv", {
      p_cv_id: CV_ID,
      p_user_id: USER_ID,
    });
  });

  it("keeps the sanitized response when storage cleanup rejects", async () => {
    const { client } = makeUploadClient({ message: "database unavailable" });
    const { client: serviceClient, rpc, referenceUpdate } = makeServiceClient({
      removeReject: new Error("storage transport failure"),
    });
    createServerClientMock.mockResolvedValue(client as never);
    createServiceClientMock.mockReturnValue(serviceClient as never);

    const responsePromise = POST(makeRequest() as never);

    await expect(responsePromise).resolves.toBeInstanceOf(Response);
    const response = await responsePromise;
    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "could not finalize cv record",
      cleanup: "incomplete",
    });
    expect(referenceUpdate).toHaveBeenCalledWith({ storage_path: CV_PATH });
    expect(rpc).not.toHaveBeenCalled();
  });

  it("keeps the sanitized response when delete_cv rejects", async () => {
    const { client } = makeUploadClient(null);
    const { client: serviceClient, remove } = makeServiceClient({
      queueError: { message: "queue unavailable" },
      rpcReject: new Error("database transport failure"),
    });
    createServerClientMock.mockResolvedValue(client as never);
    createServiceClientMock.mockReturnValue(serviceClient as never);

    const responsePromise = POST(makeRequest() as never);

    await expect(responsePromise).resolves.toBeInstanceOf(Response);
    const response = await responsePromise;
    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "could not enqueue cv extraction",
      cleanup: "incomplete",
    });
    expect(remove).toHaveBeenCalledWith([CV_PATH]);
  });
});
