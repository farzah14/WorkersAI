import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { JobActions } from "@/components/jobs/job-actions";
import { ScoreBadge } from "@/components/jobs/score-badge";
import type { JobStatus } from "@/app/api/job-status/route";
import { createClient } from "@/lib/supabase/server";

type MatchDetail = {
  id: string;
  overall_score: number;
  verdict: string;
  explanation: string;
  recommendations: string[];
  strengths: string[];
  gaps: string[];
  critical_gaps: string[];
  skills_score: number;
  experience_score: number;
  education_score: number;
  location_score: number;
  seniority_score: number;
  language_score: number;
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

const DIMENSIONS: Array<{ label: string; key: keyof Pick<MatchDetail, "skills_score" | "experience_score" | "education_score" | "location_score" | "seniority_score" | "language_score"> }> = [
  { label: "Skills", key: "skills_score" },
  { label: "Experience", key: "experience_score" },
  { label: "Seniority", key: "seniority_score" },
  { label: "Education", key: "education_score" },
  { label: "Language", key: "language_score" },
  { label: "Location", key: "location_score" },
];

export default async function JobMatchPage({
  params,
}: {
  params: Promise<{ matchId: string }>;
}) {
  const { matchId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  const { data: match } = await supabase
    .from("job_matches")
    .select(
      "id, overall_score, verdict, explanation, recommendations, strengths, gaps, critical_gaps, skills_score, experience_score, education_score, location_score, seniority_score, language_score, job_id, jobs(title, company, location, region, work_mode, employment_type, published_at, source_name, original_url)",
    )
    .eq("id", matchId)
    .maybeSingle();

  if (!match) {
    notFound();
  }

  const detail = match as unknown as MatchDetail;
  const job = detail.jobs[0];

  const { data: statusRows } = await supabase
    .from("user_jobs")
    .select("status")
    .eq("user_id", user.id)
    .eq("job_id", detail.job_id)
    .maybeSingle();
  const status = (statusRows?.status as JobStatus | undefined) ?? "new";

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">Match detail</p>
          <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">{job?.title}</h1>
              <p className="mt-2 text-lg text-[#53616a]">
                {job?.company}
                {job?.location ? ` · ${job.location}` : ""}
                {job?.work_mode ? ` · ${job.work_mode}` : ""}
              </p>
              <p className="mt-1 text-sm text-[#6d787e]">
                {job?.source_name} · published {job?.published_at?.slice(0, 10) ?? "unknown"}
              </p>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <ScoreBadge score={detail.overall_score} />
              <span className="rounded-full border border-[#d9d5cc] px-3 py-1 text-xs font-semibold capitalize text-[#53616a]">
                {detail.verdict.replaceAll("_", " ")}
              </span>
            </div>
          </div>
        </header>

        <section aria-label="Score breakdown" className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {DIMENSIONS.map((dimension) => (
            <div key={dimension.key} className="rounded-2xl border border-[#d9d5cc] bg-white p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#6d787e]">{dimension.label}</p>
              <p className="mt-2 text-2xl font-semibold tabular-nums">{detail[dimension.key]}</p>
            </div>
          ))}
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-3xl border border-[#d9d5cc] bg-white p-6">
            <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#6d787e]">Explanation</h2>
            <p className="mt-4 leading-7 text-[#15212b]">{detail.explanation}</p>

            <h3 className="mt-8 text-sm font-semibold uppercase tracking-[0.16em] text-[#6d787e]">Recommendations</h3>
            <ul className="mt-4 space-y-3">
              {detail.recommendations.map((recommendation) => (
                <li key={recommendation} className="flex gap-3 leading-6 text-[#53616a]">
                  <span aria-hidden="true" className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#d9623c]" />
                  {recommendation}
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-6">
            <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6">
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#6d787e]">Strengths</h2>
              <ul className="mt-4 space-y-2">
                {detail.strengths.map((strength) => (
                  <li key={strength} className="flex gap-3 leading-6 text-[#1f6b59]">
                    <span aria-hidden="true">✓</span>
                    {strength}
                  </li>
                ))}
                {detail.strengths.length === 0 && <li className="text-[#6d787e]">No strengths recorded.</li>}
              </ul>
            </section>

            <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6">
              <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-[#6d787e]">Gaps</h2>
              <h3 className="mt-4 text-xs font-semibold uppercase tracking-[0.14em] text-[#9b351c]">Critical</h3>
              <ul className="mt-2 space-y-2">
                {detail.critical_gaps.map((gap) => (
                  <li key={gap} className="flex gap-3 leading-6 text-[#9b351c]">
                    <span aria-hidden="true">!</span>
                    {gap}
                  </li>
                ))}
                {detail.critical_gaps.length === 0 && <li className="text-[#6d787e]">No critical gaps.</li>}
              </ul>
              <h3 className="mt-5 text-xs font-semibold uppercase tracking-[0.14em] text-[#6d787e]">Other</h3>
              <ul className="mt-2 space-y-2">
                {detail.gaps.map((gap) => (
                  <li key={gap} className="flex gap-3 leading-6 text-[#53616a]">
                    <span aria-hidden="true">—</span>
                    {gap}
                  </li>
                ))}
                {detail.gaps.length === 0 && <li className="text-[#6d787e]">No other gaps.</li>}
              </ul>
            </section>
          </div>
        </section>

        <section className="flex flex-col gap-4 rounded-3xl border border-[#d9d5cc] bg-white p-6 sm:flex-row sm:items-center sm:justify-between">
          <a
            href={job?.original_url ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex justify-center rounded-full bg-[#15212b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#263946]"
          >
            View original job
          </a>
          <JobActions jobId={detail.job_id} status={status} />
        </section>

        <p className="text-sm text-[#6d787e]">
          <Link href="/dashboard" className="font-semibold text-[#d9623c] hover:underline">
            Back to dashboard
          </Link>
        </p>
      </div>
    </main>
  );
}