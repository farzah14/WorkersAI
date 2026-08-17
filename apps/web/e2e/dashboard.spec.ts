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

  await page.getByPlaceholder("0").fill("80");
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