import { beforeEach, describe, expect, it, vi } from "vitest";

const redirectMock = vi.hoisted(() => vi.fn());
const headersMock = vi.hoisted(() => vi.fn());
const createClientMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    redirectMock(url);
    throw new Error(`REDIRECT:${url}`);
  },
}));

vi.mock("next/headers", () => ({
  headers: headersMock,
}));

vi.mock("@/lib/supabase/server", () => ({
  createClient: createClientMock,
}));

import { requestPasswordReset, updatePassword } from "@/app/(auth)/actions";
import { GET as callbackGet } from "@/app/auth/callback/route";

describe("Password recovery and callback next routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    headersMock.mockResolvedValue(new Map([["origin", "http://localhost:3000"]]));
  });

  it("redirects with missing_email if email is empty", async () => {
    const formData = new FormData();
    formData.set("email", "");

    await expect(requestPasswordReset(formData)).rejects.toThrow("REDIRECT:/forgot-password?error=missing_email");
  });

  it("requests password reset with next=/dashboard/settings callback", async () => {
    const resetPasswordForEmailMock = vi.fn().mockResolvedValue({ error: null });
    createClientMock.mockResolvedValue({
      auth: {
        resetPasswordForEmail: resetPasswordForEmailMock,
      },
    });

    const formData = new FormData();
    formData.set("email", "candidate@example.com");

    await expect(requestPasswordReset(formData)).rejects.toThrow("REDIRECT:/forgot-password?success=1");
    expect(resetPasswordForEmailMock).toHaveBeenCalledWith("candidate@example.com", {
      redirectTo: "http://localhost:3000/auth/callback?next=/dashboard/settings",
    });
  });

  it("rejects weak password update", async () => {
    createClientMock.mockResolvedValue({
      auth: {
        getUser: vi.fn().mockResolvedValue({ data: { user: { id: "user-1" } } }),
      },
    });

    const formData = new FormData();
    formData.set("password", "weak");
    formData.set("confirmPassword", "weak");

    await expect(updatePassword(formData)).rejects.toThrow("REDIRECT:/dashboard/settings?error=weak_password");
  });

  it("rejects mismatched password confirmation", async () => {
    createClientMock.mockResolvedValue({
      auth: {
        getUser: vi.fn().mockResolvedValue({ data: { user: { id: "user-1" } } }),
      },
    });

    const formData = new FormData();
    formData.set("password", "StrongP@ss1");
    formData.set("confirmPassword", "StrongP@ss2");

    await expect(updatePassword(formData)).rejects.toThrow("REDIRECT:/dashboard/settings?error=password_mismatch");
  });

  it("updates password when valid", async () => {
    const updateUserMock = vi.fn().mockResolvedValue({ error: null });
    createClientMock.mockResolvedValue({
      auth: {
        getUser: vi.fn().mockResolvedValue({ data: { user: { id: "user-1" } } }),
        updateUser: updateUserMock,
      },
    });

    const formData = new FormData();
    formData.set("password", "StrongP@ss1!");
    formData.set("confirmPassword", "StrongP@ss1!");

    await expect(updatePassword(formData)).rejects.toThrow("REDIRECT:/dashboard/settings?password_updated=1");
    expect(updateUserMock).toHaveBeenCalledWith({ password: "StrongP@ss1!" });
  });

  it("callback redirects to next param when valid", async () => {
    createClientMock.mockResolvedValue({
      auth: {
        exchangeCodeForSession: vi.fn().mockResolvedValue({ error: null }),
      },
    });

    const req = new Request("http://localhost:3000/auth/callback?code=test-code&next=/dashboard/settings");
    const response = await callbackGet(req);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/dashboard/settings");
  });

  it("callback ignores invalid next param and defaults to /dashboard", async () => {
    createClientMock.mockResolvedValue({
      auth: {
        exchangeCodeForSession: vi.fn().mockResolvedValue({ error: null }),
      },
    });

    const req = new Request("http://localhost:3000/auth/callback?code=test-code&next=https://malicious.com");
    const response = await callbackGet(req);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/dashboard");
  });
});
