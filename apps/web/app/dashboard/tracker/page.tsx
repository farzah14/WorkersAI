import Link from "next/link";
import { redirect } from "next/navigation";
import { JobActions } from "@/components/jobs/job-actions";
import { createClient } from "@/lib/supabase/server";

type TrackedJob = {
  job_id: string;
  status: "new" | "saved" | "applied" | "ignored";
  updated_at: string;
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

export default async function TrackerPage() {
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
    .select(
      "job_id, status, updated_at, jobs(title, company, location, work_mode, employment_type, published_at, source_name, original_url)"
    )
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false });

  const tracked = (rows as TrackedJob[] | null) ?? [];
  const savedJobs = tracked.filter((j) => j.status === "saved");
  const appliedJobs = tracked.filter((j) => j.status === "applied");
  const ignoredJobs = tracked.filter((j) => j.status === "ignored");

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
            Pipeline
          </p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">
            Application Tracker
          </h1>
          <p className="mt-2 text-[#53616a]">
            Keep track of every opportunity from saved bookmark to submitted application.
          </p>
        </header>

        {/* Pipeline Summary Cards */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-[#d9d5cc] bg-white p-5 shadow-[0_12px_40px_rgba(21,33,43,0.05)]">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#6d787e]">
              Saved Roles
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums tracking-[-0.03em] text-[#15212b]">
              {savedJobs.length}
            </p>
          </div>
          <div className="rounded-2xl border border-[#d9d5cc] bg-white p-5 shadow-[0_12px_40px_rgba(21,33,43,0.05)]">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#1f6b59]">
              Applied
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums tracking-[-0.03em] text-[#1f6b59]">
              {appliedJobs.length}
            </p>
          </div>
          <div className="rounded-2xl border border-[#d9d5cc] bg-white p-5 shadow-[0_12px_40px_rgba(21,33,43,0.05)]">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#6d787e]">
              Archived / Ignored
            </p>
            <p className="mt-2 text-3xl font-semibold tabular-nums tracking-[-0.03em] text-[#6d787e]">
              {ignoredJobs.length}
            </p>
          </div>
        </section>

        {/* Tracked Jobs List */}
        {tracked.length === 0 ? (
          <section className="rounded-3xl border border-[#d9d5cc] bg-white p-8 text-center shadow-[0_20px_60px_rgba(21,33,43,0.08)]">
            <h2 className="text-xl font-semibold">No tracked jobs yet</h2>
            <p className="mt-2 text-sm text-[#53616a]">
              Save or mark jobs as applied from your main dashboard feed to track them here.
            </p>
            <Link
              href="/dashboard"
              className="mt-6 inline-flex rounded-full bg-[#15212b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#263946]"
            >
              Go to Match Dashboard
            </Link>
          </section>
        ) : (
          <ul className="space-y-4">
            {tracked.map((item) => {
              const jobs = Array.isArray(item.jobs) ? item.jobs : [item.jobs];
              const job = jobs[0];
              const isApplied = item.status === "applied";
              const isSaved = item.status === "saved";

              return (
                <li
                  key={item.job_id}
                  className="rounded-2xl border border-[#d9d5cc] bg-white p-6 shadow-xs"
                >
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2.5 py-0.5 text-xs font-semibold rounded-full capitalize ${
                            isApplied
                              ? "bg-[#e5f0ec] text-[#1f6b59]"
                              : isSaved
                              ? "bg-[#fff0eb] text-[#d9623c]"
                              : "bg-[#eae7df] text-[#6d787e]"
                          }`}
                        >
                          {item.status}
                        </span>
                        <span className="text-xs text-[#6d787e] font-mono">
                          Updated {item.updated_at.slice(0, 10)}
                        </span>
                      </div>

                      <h2 className="mt-2 text-lg font-semibold text-[#15212b]">
                        {job?.title ?? "Untitled job"}
                      </h2>
                      <p className="mt-1 text-sm text-[#53616a]">
                        {job?.company ?? "—"}
                        {job?.location ? ` · ${job.location}` : ""}
                        {job?.work_mode ? ` · ${job.work_mode}` : ""}
                      </p>
                      <p className="mt-1 text-xs text-[#6d787e]">
                        {job?.source_name} · Published{" "}
                        {job?.published_at?.slice(0, 10) ?? "unknown"}
                      </p>
                    </div>

                    <div className="flex shrink-0 gap-2">
                      {job?.original_url && (
                        <a
                          href={job.original_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-full border border-[#d9d5cc] px-4 py-2 text-sm font-semibold text-[#53616a] transition hover:border-[#d9623c] hover:text-[#d9623c]"
                        >
                          View Job
                        </a>
                      )}
                      <JobActions jobId={item.job_id} status={item.status} />
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </main>
  );
}
