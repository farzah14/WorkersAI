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
          update: vi.fn().mockReturnValue({
            eq: vi.fn().mockResolvedValue({ data: null, error: pathError }),
          }),
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
  };
}

function makeServiceClient(queueError: unknown) {
  const remove = vi.fn().mockResolvedValue({ data: [], error: null });
  const rpc = vi.fn().mockResolvedValue({ data: null, error: null });

  return {
    client: {
      from: vi.fn((table: string) => {
        if (table !== "work_items") throw new Error(`unexpected table ${table}`);
        return {
          insert: vi.fn().mockResolvedValue({ data: null, error: queueError }),
        };
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
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("POST /api/cvs cleanup after storage upload", () => {
  it("removes the exact object and provisional row when storage-path persistence fails", async () => {
    const { client } = makeUploadClient({ message: "database unavailable" });
    const { client: serviceClient, remove, rpc } = makeServiceClient(null);
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

  it("removes the exact object and provisional row when queue insertion fails", async () => {
    const { client } = makeUploadClient(null);
    const {
      client: serviceClient,
      remove,
      rpc,
    } = makeServiceClient({ message: "queue unavailable" });
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
});
