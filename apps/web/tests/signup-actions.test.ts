import { beforeEach, describe, expect, it, vi } from "vitest";

const redirectMock = vi.hoisted(() =>
  vi.fn((url: string) => {
    throw new Error(`NEXT_REDIRECT:${url}`);
  }),
);

const signUpMock = vi.hoisted(() => vi.fn());
const signOutMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

vi.mock("@/lib/supabase/server", () => ({
  createClient: vi.fn().mockResolvedValue({
    auth: {
      signUp: signUpMock,
      signOut: signOutMock,
    },
  }),
}));

import { signUp } from "@/app/(auth)/actions";

const USER_ID = "00000000-0000-4000-8000-000000000001";

function validFormData(overrides: Record<string, string> = {}): FormData {
  const formData = new FormData();
  formData.set("email", overrides.email ?? "test@example.com");
  formData.set("password", overrides.password ?? "Password123!");
  formData.set("confirmPassword", overrides.confirmPassword ?? overrides.password ?? "Password123!");
  return formData;
}

describe("signUp action redirect contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects a signup with a session to the dashboard without signing out", async () => {
    signUpMock.mockResolvedValue({
      data: { user: { id: USER_ID }, session: { access_token: "test-token" } },
      error: null,
    });

    await expect(signUp(validFormData())).rejects.toThrow("NEXT_REDIRECT:/dashboard");
    expect(signOutMock).not.toHaveBeenCalled();
  });

  it("sends a sessionless signup to login", async () => {
    signUpMock.mockResolvedValue({
      data: { user: { id: USER_ID }, session: null },
      error: null,
    });

    await expect(signUp(validFormData())).rejects.toThrow("NEXT_REDIRECT:/login?registered=1");
  });

  it("redirects to register with email_taken when user already exists", async () => {
    signUpMock.mockResolvedValue({
      data: { user: null, session: null },
      error: { code: "user_already_exists" },
    });

    await expect(signUp(validFormData())).rejects.toThrow("NEXT_REDIRECT:/register?error=email_taken");
  });

  it("redirects to register with signup_failed on other errors", async () => {
    signUpMock.mockResolvedValue({
      data: { user: null, session: null },
      error: { code: "unexpected_error" },
    });

    await expect(signUp(validFormData())).rejects.toThrow("NEXT_REDIRECT:/register?error=signup_failed");
  });

  it("redirects to register on password mismatch", async () => {
    const formData = validFormData({ confirmPassword: "DifferentPassword123!" });
    await expect(signUp(formData)).rejects.toThrow("NEXT_REDIRECT:/register?error=password_mismatch");
    expect(signUpMock).not.toHaveBeenCalled();
  });

  it("redirects to register on weak password", async () => {
    const formData = validFormData({ password: "weak", confirmPassword: "weak" });
    await expect(signUp(formData)).rejects.toThrow("NEXT_REDIRECT:/register?error=weak_password");
    expect(signUpMock).not.toHaveBeenCalled();
  });
});
