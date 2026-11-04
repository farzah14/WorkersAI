import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

type SeedState = {
  userId: string;
  runId: string;
  bestMatchId: string;
  bestJobUrl: string;
};

const state = JSON.parse(
  readFileSync(path.resolve(__dirname, ".seed-state.json"), "utf8"),
) as SeedState;

test("dashboard tracking and export journey", async ({ page }) => {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/login");
  await page.getByLabel("Email").fill("e2e@example.test");
  await page.getByLabel("Password").fill("E2e-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");

  const summary = page.locator('section[aria-label="Match summary"]');
  await expect(summary.getByText("Best").locator("xpath=..").locator("p").nth(1)).toHaveText("1");
  await expect(summary.getByText("Strong").locator("xpath=..").locator("p").nth(1)).toHaveText("1");

  await page.getByRole("spinbutton", { name: "Min score" }).fill("80");
  await expect(page.locator("tbody tr")).toHaveCount(2);

  await page.getByRole("link", { name: "Data Engineer (Airflow)" }).click();
  await page.waitForURL(`**/jobs/${state.bestMatchId}`);

  await expect(
    page.getByText("Your pipeline engineering background with Airflow and SQL matches the core of this role."),
  ).toBeVisible();

  const viewJob = page.getByRole("link", { name: "View original job" });
  await expect(viewJob).toHaveAttribute("href", state.bestJobUrl);

  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: "Unsave" })).toBeVisible();

  await page.getByRole("button", { name: "Mark Applied" }).click();
  await expect(page.getByRole("button", { name: "Applied" })).toBeVisible();

  const response = await page.evaluate(async (searchRunId) => {
    const res = await fetch("/api/exports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ searchRunId, format: "xlsx", scope: "all" }),
    });
    return { status: res.status, body: await res.json() };
  }, state.runId);
  expect(response.status).toBe(202);
  expect(typeof response.body.id).toBe("string");

  await page.goto("/exports");
  await expect(page.getByRole("heading", { name: /Excel/ })).toBeVisible();
  await expect(page.getByText("Queued").first()).toBeVisible();
});
test("dashboard result filters combine and clear", async ({ page }) => {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/login");
  await page.getByLabel("Email").fill("e2e@example.test");
  await page.getByLabel("Password").fill("E2e-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");

  await expect(page.getByText("Results are for your latest search run.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Export these results" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Export Excel (.xlsx)" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Export PDF (.pdf)" })).toHaveCount(0);
  // D1: only the latest run is shown; the older run's duplicate job is absent.
  await expect(page.locator("tbody tr")).toHaveCount(4);

  const query = page.getByRole("searchbox", { name: "Search title or company" });
  await query.fill("acme");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.getByText("Data Engineer (Airflow)")).toBeVisible();

  await page.getByRole("combobox", { name: "Employment type" }).selectOption("full-time");
  await page.getByRole("combobox", { name: "Work mode" }).selectOption("remote");
  await page.getByRole("combobox", { name: "Source" }).selectOption("Greenhouse");
  await expect(page.locator("tbody tr")).toHaveCount(1);

  // Date range keeps the same job (published today).
  const today = new Date().toISOString().slice(0, 10);
  await page.getByLabel("Published from").fill(today);
  await page.getByLabel("Published to").fill(today);
  await expect(page.getByText("Showing 1 of 1 matching jobs.")).toBeVisible();

  // Reversed dates are visibly rejected without replacing the last valid filters.
  await page.getByLabel("Published from").fill("2099-01-02");
  await expect(page.getByRole("alert")).toContainText("start date must be on or before");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByLabel("Published from").fill(today);
  await expect(page.locator("tbody tr")).toHaveCount(1);

  // Explicit Ignored status shows only ignored rows and clears the exclusion.
  await page.getByRole("combobox", { name: "Status" }).selectOption("ignored");
  await expect(page.locator("tbody tr")).toHaveCount(0);
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(query).toHaveValue("");
  await expect(page.locator("tbody tr")).toHaveCount(4);

});

test("dashboard filter controls are localized in Bahasa Indonesia", async ({ page }) => {
  await page.context().addCookies([{ name: "locale", value: "id", domain: "localhost", path: "/" }]);
  await page.goto("/login");
  await page.getByLabel("Email").fill("e2e@example.test");
  await page.getByLabel("Password").fill("E2e-password-123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");

  await expect(page.getByRole("searchbox", { name: "Cari judul atau perusahaan" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Jenis pekerjaan" })).toBeVisible();
  await expect(page.getByText("Hasil ini untuk pencarian terbaru Anda.")).toBeVisible();
});
