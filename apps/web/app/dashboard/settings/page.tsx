import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { SettingsActions } from "@/app/settings/settings-actions";

type CvRow = {
  id: string;
  original_name: string | null;
  storage_path: string | null;
  retain_original: boolean;
};

export default async function DashboardSettingsPage() {
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
    .select("id, original_name, storage_path, retain_original")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const cvRows: CvRow[] = cvs ?? [];

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
            Preferences
          </p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">
            Settings & Privacy
          </h1>
          <p className="mt-2 text-[#53616a]">
            Manage your stored CV retention policies and account data.
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
                    {!cv.storage_path && (
                      <span className="ml-2 text-xs text-[#6d787e]">
                        ({t("settings.originalDeleted")})
                      </span>
                    )}
                  </p>
                </div>
                <SettingsActions cv={cv} copy={t.raw("settings")} />
              </li>
            ))}
            {cvRows.length === 0 && (
              <li className="py-4 text-sm text-[#6d787e]">
                No CVs currently stored.
              </li>
            )}
          </ul>
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
