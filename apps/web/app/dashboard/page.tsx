import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { MatchTable } from "@/components/jobs/match-table";
import { bucketForScore } from "@/lib/jobs/buckets";
import type { MatchRow, RegionValue } from "@/lib/jobs/filter";
import { createClient } from "@/lib/supabase/server";

type MatchWithJob = {
  id: string;
  overall_score: number;
  verdict: string;
  created_at: string;
  job_id: string;
  jobs: Array<{
    title: string;
    company: string;
    location: string | null;
    region: string;
    work_mode: string | null;
    employment_type: string | null;
    published_at: string | null;
    source_name: string;
    original_url: string;
  }>;
};

type StatusRow = { job_id: string; status: MatchRow["status"] };

function toMatchRow(match: MatchWithJob, status: MatchRow["status"]): MatchRow {
  const jobs = Array.isArray(match.jobs) ? match.jobs : [match.jobs];
  const job = jobs[0];
  return {
    matchId: match.id,
    jobId: match.job_id,
    title: job?.title ?? "Unknown job",
    company: job?.company ?? "—",
    location: job?.location ?? null,
    region: (job?.region ?? "unknown") as RegionValue | "unknown",
    workMode: (job?.work_mode ?? null) as MatchRow["workMode"],
    employmentType: job?.employment_type ?? null,
    publishedAt: job?.published_at ?? null,
    sourceName: job?.source_name ?? "—",
    originalUrl: job?.original_url ?? "#",
    overallScore: match.overall_score,
    status,
  };
}

export default async function DashboardPage() {
  const t = await getTranslations();
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  const { data: run } = await supabase
    .from("job_search_runs")
    .select("id, status, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (!run) {
    return (
      <main className="min-h-screen bg-[#f4f1ea] px-5 py-12 text-[#15212b] sm:px-8">
        <section className="mx-auto max-w-xl rounded-3xl border border-[#d9d5cc] bg-white p-8 text-center shadow-[0_20px_60px_rgba(21,33,43,0.08)]">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
            {t("dashboard.heading")}
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-[-0.04em]">{t("dashboard.noMatches")}</h1>
          <p className="mt-4 leading-7 text-[#53616a]">{t("dashboard.noMatchesHint")}</p>
          <Link
            href="/find-jobs"
            className="mt-8 inline-flex rounded-full bg-[#15212b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#263946]"
          >
            {t("dashboard.startSearch")}
          </Link>
        </section>
      </main>
    );
  }

  const { data: matches } = await supabase
    .from("job_matches")
    .select(
      "id, overall_score, verdict, created_at, job_id, jobs(title, company, location, region, work_mode, employment_type, published_at, source_name, original_url)",
    )
    .eq("search_run_id", run.id)
    .order("overall_score", { ascending: false });

  const { data: statusRows } = await supabase
    .from("user_jobs")
    .select("job_id, status")
    .eq("user_id", user.id);

  const statusByJob = new Map((statusRows as StatusRow[] | null)?.map((row) => [row.job_id, row.status]));
  const rows = ((matches as MatchWithJob[] | null) ?? []).map((match) =>
    toMatchRow(match, statusByJob.get(match.job_id) ?? "new"),
  );

  const today = new Date().toISOString().slice(0, 10);
  const cards = [
    { label: t("dashboard.matchScore"), value: rows.length },
    { label: t("buckets.best"), value: rows.filter((m) => bucketForScore(m.overallScore) === "best").length },
    { label: t("buckets.strong"), value: rows.filter((m) => bucketForScore(m.overallScore) === "strong").length },
    { label: t("dashboard.published"), value: rows.filter((m) => m.publishedAt?.slice(0, 10) === today).length },
  ];

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-6xl space-y-8">
        <header className="flex flex-col gap-4 border-b border-[#d9d5cc] pb-8 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
              {t("dashboard.heading")}
            </p>
            <h1 className="text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">{t("dashboard.subheading")}</h1>
          </div>
          <p className="text-sm text-[#6d787e]">
            Run <span className="font-mono">{run.id.slice(0, 8)}</span> ·{" "}
            <span className="capitalize">{t(`processing.${run.status}`)}</span>
          </p>
        </header>

        <section aria-label="Match summary" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {cards.map((card) => (
            <div
              key={card.label}
              className="rounded-2xl border border-[#d9d5cc] bg-white p-5 shadow-[0_12px_40px_rgba(21,33,43,0.05)]"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#6d787e]">{card.label}</p>
              <p className="mt-2 text-3xl font-semibold tabular-nums tracking-[-0.03em]">{card.value}</p>
            </div>
          ))}
        </section>

        <MatchTable rows={rows} />
      </div>
    </main>
  );
}