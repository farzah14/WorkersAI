import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({ default: "a" }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string) =>
    namespace === "storage" && key === "title" ? "Storage" : key,
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null } }) },
    rpc: vi.fn().mockResolvedValue({ data: null, error: null }),
  }),
}));

import { Sidebar } from "@/components/dashboard/sidebar";

describe("Sidebar", () => {
  it("does not show storage usage", () => {
    render(
      <Sidebar
        isCollapsed={false}
        isMobileOpen={false}
        onToggleCollapse={() => {}}
        onCloseMobile={() => {}}
      />,
    );

    expect(screen.queryByText("Storage", { exact: true })).not.toBeInTheDocument();
  });
});
