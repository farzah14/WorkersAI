import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";

type ExportRow = {
  id: string;
  format: string;
  scope: string;
  status: string;
  error_code: string | null;
  created_at: string | null;
  completed_at: string | null;
  storage_path: string | null;
};

const scopeKeys: Record<string, string> = {
  all: "exports.scopeAll",
  current_filters: "exports.scopeCurrentFilters",
  best_and_strong: "exports.scopeBestAndStrong",
};

export default async function ExportsPage() {
  const t = await getTranslations();
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  const { data: rows } = await supabase
    .from("exports")
    .select("id, format, scope, status, error_code, created_at, completed_at, storage_path")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const exports: Array<ExportRow & { download_url: string | null }> = [];
  for (const row of (rows as ExportRow[] | null) ?? []) {
    let downloadUrl: string | null = null;
    if (row.status === "completed" && row.storage_path) {
      const { data } = await supabase.storage.from("exports").createSignedUrl(row.storage_path, 3600);
      downloadUrl = data?.signedUrl ?? null;
    }
    exports.push({ ...row, download_url: downloadUrl });
  }

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">{t("nav.exports")}</p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em]">{t("exports.heading")}</h1>
          <p className="mt-2 text-[#53616a]">{t("exports.subheading")}</p>
        </header>

        {exports.length === 0 && (
          <section className="rounded-3xl border border-[#d9d5cc] bg-white p-8 text-center">
            <p className="leading-7 text-[#53616a]">{t("exports.emptyHint")}</p>
            <Link
              href="/dashboard"
              className="mt-6 inline-flex rounded-full bg-[#15212b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#263946]"
            >
              {t("exports.empty")}
            </Link>
          </section>
        )}

        <ul className="space-y-4">
          {exports.map((item) => {
            const scopeKey = scopeKeys[item.scope] ?? "exports.scopeAll";
            const statusKey =
              item.status === "queued"
                ? "exports.statusQueued"
                : item.status === "processing"
                  ? "exports.statusProcessing"
                  : item.status === "completed"
                    ? "exports.statusCompleted"
                    : "exports.statusFailed";
            return (
              <li key={item.id} className="rounded-2xl border border-[#d9d5cc] bg-white p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">
                      {t(item.format === "xlsx" ? "exports.xlsx" : "exports.pdf")} · {t(scopeKey)}
                    </h2>
                    <p className="mt-1 text-sm text-[#53616a]">
                      {t(statusKey)}
                      {item.error_code ? ` · ${item.error_code}` : ""}
                    </p>
                    <p className="mt-1 text-xs text-[#6d787e]">
                      {item.created_at?.slice(0, 10) ?? "—"}
                      {item.completed_at ? ` → ${item.completed_at.slice(0, 10)}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
{item.download_url ? (
                      <a
                        href={item.download_url}
                        className="rounded-full bg-[#15212b] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#263946]"
                      >
                        {t("exports.download")}
                      </a>
                    ) : (
                      <span className="rounded-full border border-[#d9d5cc] px-4 py-2 text-sm text-[#53616a]">
                        {t("exports.statusQueued")}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </main>
  );
}