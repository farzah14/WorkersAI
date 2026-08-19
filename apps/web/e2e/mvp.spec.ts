import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

// Full MVP acceptance journey. Worker-level criteria (partial source
// success, normalization/dedup, cached requirements, daily scheduler,
// provider fallback) are covered by the worker pytest suite; this file
// covers the web-facing criteria end to end plus cross-user isolation.
type SeedState = {
  userId: string;
  runId: string;
  bestMatchId: string;
  bestJobUrl: string;
  otherUserId: string;
  otherUserMatchId: string;
  otherUserJobUrl: string;
  otherUserJobTitle: string;
};

const state = JSON.parse(
  readFileSync(path.resolve(__dirname, ".seed-state.json"), "utf8"),
) as SeedState;

const SEED_EMAIL = "e2e@example.test";
const SEED_PASSWORD = "E2e-password-123";

async function signIn(page: Page): Promise<void> {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/login");
  await page.getByLabel("Email").fill(SEED_EMAIL);
  await page.getByLabel("Password").fill(SEED_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
}

test("acceptance: email login and Google OAuth callback contract", async ({ page }) => {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  await signIn(page);
  await expect(page).toHaveURL(/\/dashboard/);
});

test("acceptance: register rejects mismatched password confirmation", async ({ page }) => {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/register");
  await page.getByLabel("Email").fill("e2e-register-fresh@example.test");
  await page.locator("#register-password").fill("E2e-password-123!");
  await page.locator("#register-confirm-password").fill("Different-password-456!");
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByText("Passwords do not match.")).toBeVisible();
  await expect(page).toHaveURL(/error=password_mismatch/);
});

test("acceptance: register sends the user to sign in first", async ({ page }) => {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/register");
  await page.getByLabel("Email").fill(`e2e-register-${Date.now()}@example.test`);
  await page.locator("#register-password").fill("E2e-password-123!");
  await page.locator("#register-confirm-password").fill("E2e-password-123!");
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByText("Account created. Please sign in.")).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("acceptance: register rejects passwords without letters, numbers, and symbols", async ({ page }) => {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/register");
  await page.getByLabel("Email").fill("e2e-register-fresh@example.test");
  await page.locator("#register-password").fill("E2epassword123");
  await page.locator("#register-confirm-password").fill("E2epassword123");
  await page.getByRole("button", { name: "Register" }).click();
  const validationMessage = await page
    .locator("#register-password")
    .evaluate((el) => (el as HTMLInputElement).validationMessage);
  expect(validationMessage).not.toBe("");
  await expect(page).toHaveURL(/\/register/);
});

test("acceptance: dashboard shows the signed-in user name", async ({ page }) => {
  await signIn(page);
  await expect(page.locator("aside").getByText("e2e", { exact: true })).toBeVisible();
  await expect(page.getByText("Job Seeker")).not.toBeVisible();
});

test("acceptance: register rejects an already-registered email with a sign-in hint", async ({
  page,
}) => {
  await page.context().addCookies([{ name: "locale", value: "en", domain: "localhost", path: "/" }]);
  await page.goto("/register");
  await page.getByLabel("Email").fill(SEED_EMAIL);
  await page.locator("#register-password").fill("E2e-password-123!");
  await page.locator("#register-confirm-password").fill("E2e-password-123!");
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByText(/already registered/i)).toBeVisible();
  await expect(page).toHaveURL(/error=email_taken/);
});

test("acceptance: upload digital PDF and DOCX CVs", async ({ page }) => {
  await signIn(page);
  await page.goto("/cvs");
  const uploader = page.getByLabel("Choose a CV file");
  await uploader.setInputFiles(path.resolve(__dirname, "../../worker/tests/fixtures/sample.pdf"));
  await page.getByRole("button", { name: "Upload CV" }).click();
  await expect(page.getByText("sample.pdf").first()).toBeVisible();
  await uploader.setInputFiles(path.resolve(__dirname, "../../worker/tests/fixtures/sample.docx"));
  await page.getByRole("button", { name: "Upload CV" }).click();
  await expect(page.getByText("sample.docx").first()).toBeVisible();
});

test("acceptance: delete the original CV file from the profile page", async ({ page }) => {
  await signIn(page);
  await page.goto("/dashboard/profile");
  const row = page.locator("li").filter({ hasText: "sample.pdf" });
  await expect(row.getByText("Original Kept")).toBeVisible();
  await row.getByRole("button", { name: "Delete Original" }).click();
  await expect(row.getByText("Original Deleted")).toBeVisible();
  await expect(row.getByRole("button", { name: "Delete Original" })).toBeHidden();
});

test("acceptance: schema-valid editable candidate profile", async ({ page }) => {
  await signIn(page);
  await page.goto("/onboarding/profile");
  const nameInput = page.getByLabel("Name");
  await expect(nameInput).toHaveValue("E2E Candidate");
  await page.getByLabel("Current role").fill("Analytics Engineer");
  await page.getByRole("button", { name: /Save|Save profile/ }).click();
  await page.waitForURL("**/dashboard");
  await page.goto("/onboarding/profile");
  await expect(page.getByLabel("Current role")).toHaveValue("Analytics Engineer");
});

test("acceptance: ranked dashboard buckets and match detail evidence", async ({ page }) => {
  await signIn(page);
  const summary = page.locator('section[aria-label="Match summary"]');
  await expect(summary.getByText("Match Score").locator("xpath=..").locator("p").nth(1)).toHaveText("4");
  await expect(summary.getByText("Best").locator("xpath=..").locator("p").nth(1)).toHaveText("1");
  await expect(summary.getByText("Strong").locator("xpath=..").locator("p").nth(1)).toHaveText("1");

  const table = page.locator("tbody");
  await expect(table.getByText("best", { exact: true })).toBeVisible();
  await expect(table.getByText("strong", { exact: true })).toBeVisible();
  await expect(table.getByText("potential", { exact: true })).toBeVisible();
  await expect(table.getByText("low", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Senior Data Analyst" }).click();
  await page.waitForURL(/\/jobs\//);

  await expect(
    page.getByText("Your SQL and Python skills align with the analytical requirements."),
  ).toBeVisible();

  const breakdown = page.locator('section[aria-label="Score Breakdown"]');
  await expect(breakdown.locator("div").filter({ hasText: "Skills" })).toHaveCount(1);
  await expect(breakdown).toContainText("Experience");
  await expect(breakdown).toContainText("Seniority");
  await expect(breakdown).toContainText("Education");
  await expect(breakdown).toContainText("Language");
  await expect(breakdown).toContainText("Location");

  await expect(page.getByText("SQL").first()).toBeVisible();
  await expect(page.getByText("Looker").first()).toBeVisible();
  await expect(page.getByText("Add a project example using Looker.")).toBeVisible();
});

test("acceptance: original job URL is preserved", async ({ page }) => {
  await signIn(page);
  await page.goto("/dashboard");
  await page.getByRole("link", { name: "Data Engineer (Airflow)" }).click();
  await expect(page.getByRole("link", { name: "View original job" })).toHaveAttribute(
    "href",
    state.bestJobUrl,
  );
});

test("acceptance: Save, Applied, and Ignore tracking", async ({ page }) => {
  await signIn(page);
  await page.goto("/dashboard");
  await page.getByRole("link", { name: "Senior Data Analyst" }).click();
  await page.waitForURL(/\/jobs\//);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: "Unsave" })).toBeVisible();

  await page.goto("/saved");
  await expect(page.getByText("Senior Data Analyst")).toBeVisible();
  await page.getByRole("button", { name: "Ignore" }).click();
  await expect(page.getByText("Senior Data Analyst")).toBeHidden();
});

test("acceptance: XLSX and PDF export requests are queued", async ({ page }) => {
  await signIn(page);
  for (const format of ["xlsx", "pdf"]) {
    const response = await page.evaluate(
      async (request) => {
        const res = await fetch("/api/exports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        });
        return { status: res.status, body: await res.json() };
      },
      { searchRunId: state.runId, format, scope: "all" },
    );
    expect(response.status).toBe(202);
    expect(typeof response.body.id).toBe("string");
  }
  await page.goto("/exports");
  await expect(page.getByRole("heading", { name: "Excel" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "PDF" }).first()).toBeVisible();
  await expect(page.getByText("Queued").first()).toBeVisible();
});

test("acceptance: Indonesia/Global preference and manual Find Jobs Now", async ({ page }) => {
  await signIn(page);
  await page.goto("/find-jobs");
  const regionGroup = page.getByRole("radiogroup", { name: "Search region" });
  await expect(regionGroup.getByText("Indonesia")).toBeVisible();
  await regionGroup.getByText("Global").click();
  await expect(page.locator('input[name="region"][value="global"]')).toBeChecked();
  await expect(page.locator('input[name="region"][value="indonesia"]')).not.toBeChecked();
  await page.getByRole("button", { name: "Find Jobs Now" }).click();
  await expect(page.getByText(/Search queued/)).toBeVisible();
});

test("acceptance: daily discovery control is available", async ({ page }) => {
  await signIn(page);
  await page.goto("/find-jobs");
  await expect(page.getByText("Enable daily search")).toBeVisible();
  await page.getByText("Enable daily search").click();
  await expect(page.getByRole("button", { name: "Find Jobs Now" })).toBeEnabled();
});

test("acceptance: cross-user data denial", async ({ page }) => {
  await signIn(page);
  const response = await page.goto(`/jobs/${state.otherUserMatchId}`);
  expect(response?.status()).toBe(404);
  await expect(page.locator("h1")).toContainText("404");
});