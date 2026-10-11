import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { SettingsActions } from "@/app/settings/settings-actions";
import { updatePassword } from "@/app/(auth)/actions";
type CvRow = {
  id: string;
  original_name: string | null;
};

export default async function DashboardSettingsPage({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string; password_updated?: string }>;
}) {
  const { error, password_updated } = (await searchParams) ?? {};
  const t = await getTranslations();
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  const { data: cvs } = await supabase
    .from("cvs")
    .select("id, original_name")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const cvRows: CvRow[] = cvs ?? [];

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
            {t("settings.preferencesTag")}
          </p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">
            {t("settings.dashboardSettingsTitle")}
          </h1>
          <p className="mt-2 text-[#53616a]">
            {t("settings.dashboardSettingsDesc")}
          </p>
        </header>

        {/* CV Retention Policy */}
        <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6 sm:p-8 shadow-[0_12px_40px_rgba(21,33,43,0.05)] space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-[#15212b]">
              {t("settings.cvsHeading")}
            </h2>
            <p className="mt-1 text-xs text-[#53616a]">{t("settings.cvsHint")}</p>
          </div>

          <ul className="divide-y divide-[#eae7df]">
            {cvRows.map((cv) => (
              <li
                key={cv.id}
                className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-[#15212b]">
                    {cv.original_name ?? cv.id}
                  </p>
                </div>
                <SettingsActions cv={cv} copy={t.raw("settings")} />
              </li>
            ))}
            {cvRows.length === 0 && (
              <li className="py-4 text-sm text-[#6d787e]">
                {t("settings.noStoredCvs")}
              </li>
            )}
          </ul>
        </section>

        {/* Security & Password */}
        <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6 sm:p-8 shadow-[0_12px_40px_rgba(21,33,43,0.05)] space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-[#15212b]">
              {t("auth.newPasswordHeading")}
            </h2>
            <p className="mt-1 text-xs text-[#53616a]">
              {t("auth.passwordRequirementsHint")}
            </p>
          </div>

          {password_updated === "1" && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">
              {t("auth.passwordUpdated")}
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
              {error === "password_mismatch"
                ? t("auth.errors.passwordMismatch")
                : error === "weak_password"
                  ? t("auth.errors.passwordRequirements")
                  : error === "update_password_failed"
                    ? t("auth.errors.updatePasswordFailed")
                    : t("auth.errors.default")}
            </div>
          )}

          <form action={updatePassword} className="space-y-4 max-w-md">
            <div>
              <label htmlFor="settings-password" className="block text-xs font-semibold uppercase tracking-wider text-[#6d787e] mb-1">
                {t("auth.passwordLabel")}
              </label>
              <input
                id="settings-password"
                name="password"
                type="password"
                required
                placeholder={t("auth.passwordPlaceholder")}
                className="w-full rounded-xl border border-[#d9d5cc] bg-[#faf9f6] px-3.5 py-2.5 text-sm text-[#15212b] focus:border-[#d9623c] focus:outline-none focus:ring-1 focus:ring-[#d9623c]"
              />
            </div>

            <div>
              <label htmlFor="settings-confirm-password" className="block text-xs font-semibold uppercase tracking-wider text-[#6d787e] mb-1">
                {t("auth.confirmPasswordLabel")}
              </label>
              <input
                id="settings-confirm-password"
                name="confirmPassword"
                type="password"
                required
                placeholder={t("auth.confirmPasswordPlaceholder")}
                className="w-full rounded-xl border border-[#d9d5cc] bg-[#faf9f6] px-3.5 py-2.5 text-sm text-[#15212b] focus:border-[#d9623c] focus:outline-none focus:ring-1 focus:ring-[#d9623c]"
              />
            </div>

            <button
              type="submit"
              className="inline-flex items-center justify-center rounded-full bg-[#15212b] px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-[#263946]"
            >
              {t("auth.updatePasswordSubmit")}
            </button>
          </form>
        </section>
        {/* Danger Zone: Delete Account */}
        <section className="rounded-3xl border border-rose-200 bg-rose-50/50 p-6 sm:p-8 space-y-4">
          <div>
            <h2 className="text-xl font-semibold text-rose-900">
              {t("settings.accountHeading")}
            </h2>
            <p className="mt-1 text-xs text-rose-700">
              {t("settings.accountHint")}
            </p>
          </div>
          <SettingsActions account copy={t.raw("settings")} />
        </section>
      </div>
    </main>
  );
}
