import { describe, expect, it } from "vitest";
import { requiresAuth } from "@/lib/auth/routes";

describe("requiresAuth", () => {
  it("protects dashboard and cv routes", () => {
    expect(requiresAuth("/dashboard")).toBe(true);
    expect(requiresAuth("/cvs")).toBe(true);
    expect(requiresAuth("/login")).toBe(false);
  });
});