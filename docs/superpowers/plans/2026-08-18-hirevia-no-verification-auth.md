# Hirevia No-Verification Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Hirevia authentication verification-free for the MVP while requiring new users to enter Email, Password, and Confirm Password before an account is created and immediately signed in.

**Architecture:** Keep the existing Supabase Auth email/password and Google OAuth architecture. Email/password registration continues through `supabase.auth.signUp()` with Supabase email confirmations disabled; successful registration proceeds directly to `/dashboard`. Confirm Password is a Hirevia form/server-validation concern only and is never persisted or sent to Supabase. Sign-in remains Email + Password with no OTP, email confirmation, SMS, TOTP, phone, or identity-verification stage.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Supabase Auth via `@supabase/ssr` and `@supabase/supabase-js`, Playwright, Vitest, pnpm.

---

## Scope and Locked Behavior

### New-user sign-up

```text
/register
  -> Email
  -> Password
  -> Confirm Password
  -> passwords must match
  -> Supabase Auth signUp(email, password)
  -> authenticated session created immediately
  -> /dashboard
```

### Returning-user sign-in

```text
/login
  -> Email
  -> Password
  -> Supabase Auth signInWithPassword(email, password)
  -> /dashboard
```

### Google OAuth

```text
Continue with Google
  -> existing Google OAuth flow
  -> existing /auth/callback
  -> /dashboard
```

### Explicitly out of scope

Do not add any of the following in this implementation:

- email confirmation links;
- 6-digit email OTP;
- magic-link authentication;
- SMS OTP;
- phone verification;
- TOTP/authenticator verification;
- MFA enrollment;
- CAPTCHA as an account-verification stage;
- identity/KYC verification;
- custom SMTP or transactional-email provider integration;
- verification pages such as `/verify-email` or `/verify-otp`;
- changes to Google OAuth behavior;
- changes to the existing technical architecture or database schema.

## Current-State Notes

The existing server action already calls `supabase.auth.signUp({ email, password })` and redirects to `/dashboard` on success. The existing local Supabase configuration already has email signups enabled and `enable_confirmations = false`. The registration UI currently has Email and Password but does not have Confirm Password. The login UI already uses Email + Password and does not need behavior changes for this feature.

## File Structure

### Create

- `apps/web/e2e/signup-no-verification.spec.ts`
  - End-to-end regression coverage for password mismatch and successful direct-to-dashboard registration.

### Modify

- `apps/web/app/(auth)/actions.ts`
  - Read `confirmPassword` during sign-up.
  - Reject mismatched passwords before calling Supabase.
  - Preserve existing direct `/dashboard` redirect after successful `signUp()`.

- `apps/web/app/(auth)/register/page.tsx`
  - Add Confirm Password input.
  - Show a specific password-mismatch error.
  - Preserve Google OAuth and the existing sign-in link.

- `docs/superpowers/specs/2026-08-18-hirevia-prd.md`
  - Record the approved MVP policy that email/password users are not required to complete an additional verification stage.

### Verify but do not modify unless the repository has drifted

- `supabase/config.toml`
  - `enable_signup = true`
  - `[auth.email] enable_signup = true`
  - `[auth.email] enable_confirmations = false`

- `apps/web/app/(auth)/login/page.tsx`
  - Remains Email + Password.

- `apps/web/app/auth/callback/route.ts`
  - Google OAuth callback remains unchanged.

### Do not modify

- `docs/superpowers/specs/2026-08-16-ai-job-matcher-saas-design.md`
  - Keep the previous approved technical/design baseline intact.

---

### Task 1: Add a failing end-to-end sign-up specification

**Files:**
- Create: `apps/web/e2e/signup-no-verification.spec.ts`
- Test: `apps/web/e2e/signup-no-verification.spec.ts`

- [ ] **Step 1: Create the E2E test with cleanup for its dedicated test user**

Create `apps/web/e2e/signup-no-verification.spec.ts` with:

```ts
import { expect, test } from "@playwright/test";
import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "node:fs";
import path from "node:path";

const TEST_EMAIL = "e2e-signup-no-verification@example.test";
const TEST_PASSWORD = "E2e-password-123";

function loadEnvFile(): void {
  const envPath = path.resolve(__dirname, "../.env");
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const separator = trimmed.indexOf("=");
    const key = trimmed.slice(0, separator);
    const value = trimmed.slice(separator + 1).replace(/^["']|["']$/g, "");
    if (!process.env[key]) process.env[key] = value;
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing environment variable ${name} for Playwright auth test.`);
  return value;
}

async function deleteTestUser(): Promise<void> {
  loadEnvFile();
  const admin = createClient(
    requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requireEnv("SUPABASE_SERVICE_ROLE_KEY"),
    { auth: { persistSession: false } },
  );

  const {
    data: { users },
    error,
  } = await admin.auth.admin.listUsers({ perPage: 1000 });
  if (error) throw error;

  const existing = users.find((user) => user.email === TEST_EMAIL);
  if (!existing) return;

  const { error: deleteError } = await admin.auth.admin.deleteUser(existing.id);
  if (deleteError) throw deleteError;
}

test.beforeEach(async () => {
  await deleteTestUser();
});

test.afterEach(async () => {
  await deleteTestUser();
});

test("requires matching passwords and signs up without a verification step", async ({ page }) => {
  await page.goto("/register");

  await page.getByLabel("Email").fill(TEST_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel("Confirm Password").fill(`${TEST_PASSWORD}-mismatch`);
  await page.getByRole("button", { name: "Register" }).click();

  await expect(page).toHaveURL(/\/register\?error=password_mismatch$/);
  await expect(page.getByText("Passwords do not match.")).toBeVisible();

  await page.getByLabel("Email").fill(TEST_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel("Confirm Password").fill(TEST_PASSWORD);
  await page.getByRole("button", { name: "Register" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
});
```

- [ ] **Step 2: Run only this test and verify RED**

Run from the repository root:

```bash
pnpm --dir apps/web exec playwright test e2e/signup-no-verification.spec.ts
```

Expected: **FAIL** because the current registration page has no `Confirm Password` field and the current server action does not implement the `password_mismatch` behavior.

Do not modify the test to make the existing implementation pass.

---

### Task 2: Enforce Confirm Password in the server sign-up action

**Files:**
- Modify: `apps/web/app/(auth)/actions.ts`
- Test: `apps/web/e2e/signup-no-verification.spec.ts`

- [ ] **Step 1: Update only the `signUp` server action**

Replace the existing `signUp` function with:

```ts
export async function signUp(formData: FormData) {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirmPassword") ?? "");

  if (password !== confirmPassword) {
    redirect("/register?error=password_mismatch");
  }

  const { error } = await supabase.auth.signUp({ email, password });
  if (error) redirect("/register?error=signup_failed");
  redirect("/dashboard");
}
```

Do not change `signIn` or `signInWithGoogle` in this task.

The server-side comparison is required even though the UI also collects both fields. Client-side controls alone must not be treated as authorization or validation boundaries.

- [ ] **Step 2: Do not add any verification call**

The final sign-up path in `actions.ts` must still contain only the password registration call:

```ts
await supabase.auth.signUp({ email, password });
```

Do not add calls such as:

```ts
supabase.auth.signInWithOtp(...)
supabase.auth.verifyOtp(...)
supabase.auth.mfa.enroll(...)
supabase.auth.mfa.challenge(...)
supabase.auth.mfa.verify(...)
```

Do not add a redirect to `/verify-email`, `/verify-otp`, or similar routes.

---

### Task 3: Add Confirm Password to the registration UI

**Files:**
- Modify: `apps/web/app/(auth)/register/page.tsx`
- Test: `apps/web/e2e/signup-no-verification.spec.ts`

- [ ] **Step 1: Add a specific error message for password mismatch**

Immediately after reading `searchParams`, add:

```ts
const errorMessage =
  error === "password_mismatch"
    ? "Passwords do not match."
    : error
      ? "Registration failed. Please try again."
      : null;
```

Replace:

```tsx
{error && <p className="text-sm text-red-600">Registration failed. Please try again.</p>}
```

with:

```tsx
{errorMessage && <p className="text-sm text-red-600">{errorMessage}</p>}
```

- [ ] **Step 2: Add the Confirm Password field immediately after Password**

Add:

```tsx
<label className="flex flex-col gap-1 text-sm">
  Confirm Password
  <input
    name="confirmPassword"
    type="password"
    required
    minLength={6}
    autoComplete="new-password"
    className="rounded border border-gray-300 px-3 py-2"
  />
</label>
```

Keep the existing Email, Password, Register, Continue with Google, and Sign in controls.

Do not add verification-related text or controls.

- [ ] **Step 3: Run the E2E test and verify GREEN**

Run:

```bash
pnpm --dir apps/web exec playwright test e2e/signup-no-verification.spec.ts
```

Expected: **PASS**.

The test demonstrates both required behavior branches:

1. mismatched passwords return to `/register?error=password_mismatch` without creating a user;
2. matching passwords create the account and navigate directly to `/dashboard`, with no verification page in between.

- [ ] **Step 4: Commit the tested feature**

```bash
git add apps/web/app/'(auth)'/actions.ts apps/web/app/'(auth)'/register/page.tsx apps/web/e2e/signup-no-verification.spec.ts
git commit -m "feat: require password confirmation on signup"
```

---

### Task 4: Verify the no-verification Supabase configuration invariant

**Files:**
- Verify: `supabase/config.toml`
- No source modification expected.

- [ ] **Step 1: Verify local email/password signup remains enabled**

Confirm `supabase/config.toml` contains:

```toml
[auth]
enable_signup = true
```

and:

```toml
[auth.email]
enable_signup = true
```

- [ ] **Step 2: Verify local email confirmation remains disabled**

Confirm:

```toml
[auth.email]
enable_confirmations = false
```

Expected: this is already the repository state. Do **not** make a formatting-only config change.

- [ ] **Step 3: Verify the hosted Supabase project before deployment**

In the production Supabase Auth configuration, ensure the equivalent email-confirmation setting is **OFF** while email/password signup is **ON**.

Acceptance condition:

```text
successful email/password signUp()
  -> authenticated session available immediately
  -> Hirevia /dashboard accessible immediately
```

If production has email confirmation enabled, stop deployment and correct the hosted Auth setting. Do not work around the mismatch by adding OTP/email-verification code to Hirevia.

- [ ] **Step 4: Confirm no verification infrastructure is required**

For this MVP auth policy, do not add:

```text
SMTP provider
custom email domain
verification email template
OTP template
SMS provider
TOTP enrollment
verification database table
```

No commit is expected for this task unless configuration drift is actually discovered.

---

### Task 5: Confirm sign-in and Google OAuth were not changed

**Files:**
- Verify: `apps/web/app/(auth)/actions.ts`
- Verify: `apps/web/app/(auth)/login/page.tsx`
- Verify: `apps/web/app/auth/callback/route.ts`

- [ ] **Step 1: Confirm password sign-in remains unchanged**

The sign-in server action must remain equivalent to:

```ts
export async function signIn(formData: FormData) {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) redirect("/login?error=invalid_credentials");
  redirect("/dashboard");
}
```

- [ ] **Step 2: Confirm login UI remains Email + Password**

The login form must not gain a Confirm Password field. Confirm Password applies only when creating an account.

The login journey stays:

```text
Email + Password -> Sign in -> Dashboard
```

- [ ] **Step 3: Confirm Google OAuth remains unchanged**

Do not alter `signInWithGoogle()` or the existing callback route as part of this feature.

---

### Task 6: Record the approved authentication policy in the Hirevia PRD

**Files:**
- Modify: `docs/superpowers/specs/2026-08-18-hirevia-prd.md`
- Do not modify: `docs/superpowers/specs/2026-08-16-ai-job-matcher-saas-design.md`

- [ ] **Step 1: Add an MVP account-verification subsection under Authentication**

Add the following product requirement to the Hirevia PRD:

```markdown
### 8.1.1 MVP account verification policy

For the initial Hirevia MVP, email/password registration does not require a separate account-verification stage.

New users provide:

- email;
- password;
- password confirmation.

Password confirmation is validated by Hirevia before account creation and is not stored as a separate credential.

After successful Supabase email/password registration, the user proceeds directly into the authenticated application.

The initial MVP does not require:

- email confirmation links;
- email OTP;
- SMS OTP;
- phone verification;
- authenticator/TOTP verification;
- identity/KYC verification.

Returning email/password users sign in with email and password. Google OAuth remains supported separately.

Because email confirmation is intentionally disabled for the MVP, Hirevia must not treat an email/password user's email address as independently verified proof of email ownership.
```

- [ ] **Step 2: Preserve the technical baseline statement**

Do not change the PRD's rule that the previous technical design remains the source of truth for architecture, infrastructure, providers, data model, security boundaries, reliability, and testing decisions.

- [ ] **Step 3: Commit the documentation decision separately**

```bash
git add docs/superpowers/specs/2026-08-18-hirevia-prd.md
git commit -m "docs: define Hirevia MVP auth verification policy"
```

---

### Task 7: Run the web verification suite

**Files:**
- Verify all files changed by Tasks 1-6.

- [ ] **Step 1: Run the targeted E2E authentication test**

```bash
pnpm --dir apps/web exec playwright test e2e/signup-no-verification.spec.ts
```

Expected: PASS.

- [ ] **Step 2: Run the existing Vitest suite**

```bash
pnpm --dir apps/web test
```

Expected: all tests PASS.

- [ ] **Step 3: Run TypeScript checking**

```bash
pnpm --dir apps/web typecheck
```

Expected: exit code 0 with no TypeScript errors.

- [ ] **Step 4: Run ESLint**

```bash
pnpm --dir apps/web lint
```

Expected: exit code 0 with no lint errors introduced by this change.

- [ ] **Step 5: Run the production build**

```bash
pnpm --dir apps/web build
```

Expected: successful Next.js production build.

- [ ] **Step 6: Review the final diff for forbidden verification functionality**

Run:

```bash
git diff HEAD~2 -- apps/web supabase docs/superpowers/specs/2026-08-18-hirevia-prd.md
```

Verify that the feature diff contains no new OTP, verification-page, SMTP, SMS, TOTP, or MFA implementation.

- [ ] **Step 7: Check working tree cleanliness**

```bash
git status --short
```

Expected: no uncommitted files from the implementation.

---

## Acceptance Criteria

The implementation is complete only when all of the following are true:

- [ ] `/register` contains Email, Password, and Confirm Password.
- [ ] Password and Confirm Password must match before Supabase account creation is attempted.
- [ ] Confirm Password is never persisted and is never sent to Supabase.
- [ ] A successful email/password sign-up navigates directly to `/dashboard`.
- [ ] No email-confirmation, OTP, SMS, phone, TOTP, MFA, or KYC stage exists in the sign-up journey.
- [ ] `/login` remains Email + Password only.
- [ ] Google OAuth behavior remains unchanged.
- [ ] Local Supabase email confirmation remains disabled.
- [ ] Production Supabase email confirmation is verified as disabled before deployment.
- [ ] The E2E test proves password mismatch rejection and direct-to-dashboard registration.
- [ ] Existing web tests, typecheck, lint, and production build pass.
- [ ] The Hirevia PRD explicitly records the no-verification MVP policy.
- [ ] The previous `2026-08-16-ai-job-matcher-saas-design.md` technical/design baseline remains untouched.

## Self-Review

### Spec coverage

- New-user Email + Password + Confirm Password: covered by Tasks 1-3.
- No verification after account creation: covered by Tasks 1, 2, and 4.
- Returning-user Email + Password: protected from unintended change by Task 5.
- Google OAuth unchanged: protected by Task 5.
- Production/local Supabase confirmation-disabled requirement: covered by Task 4.
- Product documentation: covered by Task 6.
- Regression and build verification: covered by Task 7.

### Placeholder scan

The plan contains no deferred implementation placeholders. All planned code changes, commands, expected behaviors, and configuration invariants are specified explicitly.

### Type and naming consistency

- Form field name is consistently `confirmPassword`.
- Error query value is consistently `password_mismatch`.
- Mismatch UI text is consistently `Passwords do not match.`
- Existing `signUp`, `signIn`, and `signInWithGoogle` function names remain unchanged.
