import { describe, expect, it } from "vitest";
import { requiresAuth } from "@/lib/auth/routes";

describe("requiresAuth", () => {
  it("protects dashboard and cv routes", () => {
    expect(requiresAuth("/dashboard")).toBe(true);
    expect(requiresAuth("/cvs")).toBe(true);
    expect(requiresAuth("/login")).toBe(false);
  });

  it("protects candidate search, onboarding, saved and application routes", () => {
    expect(requiresAuth("/find-jobs")).toBe(true);
    expect(requiresAuth("/onboarding")).toBe(true);
    expect(requiresAuth("/onboarding/profile")).toBe(true);
    expect(requiresAuth("/saved")).toBe(true);
    expect(requiresAuth("/applications")).toBe(true);
  });

  it("permits public routes", () => {
    expect(requiresAuth("/")).toBe(false);
    expect(requiresAuth("/login")).toBe(false);
    expect(requiresAuth("/register")).toBe(false);
    expect(requiresAuth("/auth/callback")).toBe(false);
  });
});