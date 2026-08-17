import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { JobActions } from "@/components/jobs/job-actions";
import { createClient } from "@/lib/supabase/server";

type AppliedJob = {
  job_id: string;
  applied_at: string | null;
  jobs: Array<{
    title: string;
    company: string;
    location: string | null;
    work_mode: string | null;
    employment_type: string | null;
    published_at: string | null;
    source_name: string;
    original_url: string;
  }>;
};

export default async function ApplicationsPage() {
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
    .from("user_jobs")
    .select("job_id, applied_at, jobs(title, company, location, work_mode, employment_type, published_at, source_name, original_url)")
    .eq("user_id", user.id)
    .eq("status", "applied")
    .order("applied_at", { ascending: false });

  const applied = (rows as AppliedJob[] | null) ?? [];

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">{t("nav.applications")}</p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em]">{t("applications.heading")}</h1>
        </header>

        {applied.length === 0 && (
          <section className="rounded-3xl border border-[#d9d5cc] bg-white p-8 text-center">
            <p className="leading-7 text-[#53616a]">{t("applications.emptyHint")}</p>
            <Link
              href="/dashboard"
              className="mt-6 inline-flex rounded-full bg-[#15212b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#263946]"
            >
              {t("applications.openDashboard")}
            </Link>
          </section>
        )}

        <ul className="space-y-4">
          {applied.map((item) => {
            const jobs = Array.isArray(item.jobs) ? item.jobs : [item.jobs];
            const job = jobs[0];
            return (
              <li key={item.job_id} className="rounded-2xl border border-[#d9d5cc] bg-white p-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">{job?.title}</h2>
                    <p className="mt-1 text-sm text-[#53616a]">
                      {job?.company}
                      {job?.location ? ` · ${job.location}` : ""}
                      {job?.work_mode ? ` · ${job.work_mode}` : ""}
                    </p>
                    <p className="mt-1 text-xs text-[#6d787e]">
                      {job?.source_name} · {t("applications.appliedOn")} {item.applied_at?.slice(0, 10) ?? "unknown"}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <a
                      href={job?.original_url ?? "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-full border border-[#d9d5cc] px-4 py-2 text-sm font-semibold text-[#53616a] transition hover:border-[#d9623c] hover:text-[#d9623c]"
                    >
                      View Job
                    </a>
                    <JobActions jobId={item.job_id} status="applied" />
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