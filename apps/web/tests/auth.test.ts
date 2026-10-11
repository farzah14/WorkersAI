import { describe, expect, it, vi } from "vitest";
import { requiresAuth } from "@/lib/auth/routes";
import CvsPage from "@/app/cvs/page";
import SettingsPage from "@/app/settings/page";
import SavedJobsPage from "@/app/saved/page";
import ApplicationsPage from "@/app/applications/page";

const redirectMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  redirect: (to: string) => redirectMock(to),
}));

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
    expect(requiresAuth("/forgot-password")).toBe(false);
  });

  it("redirects legacy routes to dashboard equivalents", async () => {
    await CvsPage();
    expect(redirectMock).toHaveBeenCalledWith("/dashboard/profile");

    await SettingsPage();
    expect(redirectMock).toHaveBeenCalledWith("/dashboard/settings");

    await SavedJobsPage();
    expect(redirectMock).toHaveBeenCalledWith("/dashboard/tracker");

    await ApplicationsPage();
    expect(redirectMock).toHaveBeenCalledWith("/dashboard/tracker");
  });
});