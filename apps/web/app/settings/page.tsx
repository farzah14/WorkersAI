import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { SettingsActions } from "./settings-actions";

type CvRow = {
  id: string;
  original_name: string | null;
  storage_path: string | null;
  retain_original: boolean;
};

export default async function SettingsPage() {
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
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold">{t("settings.title")}</h1>
      <p className="mt-1 text-sm text-stone-500">{t("settings.subheading")}</p>

      <section className="mt-8">
        <h2 className="text-lg font-medium">{t("settings.cvsHeading")}</h2>
        <p className="mt-1 text-sm text-stone-500">{t("settings.cvsHint")}</p>
        <ul className="mt-4 divide-y divide-stone-200">
          {cvRows.map((cv) => (
            <li key={cv.id} className="flex items-center justify-between py-3">
              <div>
                <p className="text-sm font-medium">
                  {cv.original_name ?? cv.id}
                  {!cv.storage_path && (
                    <span className="ml-2 text-xs text-stone-400">
                      {t("settings.originalDeleted")}
                    </span>
                  )}
                </p>
              </div>
              <SettingsActions cv={cv} copy={t.raw("settings")} />
            </li>
          ))}
          {cvRows.length === 0 && (
            <li className="py-3 text-sm text-stone-400">{t("exports.empty")}</li>
          )}
        </ul>
      </section>

      <section className="mt-12 rounded-lg border border-red-200 bg-red-50 p-4">
        <h2 className="text-lg font-medium text-red-800">{t("settings.accountHeading")}</h2>
        <p className="mt-1 text-sm text-red-700">{t("settings.accountHint")}</p>
        <SettingsActions account copy={t.raw("settings")} />
      </section>
    </main>
  );
}