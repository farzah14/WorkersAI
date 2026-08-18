"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type SearchRunStatus = "queued" | "processing" | "completed" | "partial" | "failed";

type SearchRun = {
  id: string;
  trigger: string;
  status: SearchRunStatus;
  created_at: string;
};

const terminalStatuses = new Set<SearchRunStatus>(["completed", "partial", "failed"]);

export function DashboardRunStatus({
  active,
  copy,
}: {
  active: boolean;
  copy: {
    title: string;
    hint: string;
    refresh: string;
  };
}) {
  const router = useRouter();

  useEffect(() => {
    if (!active) return;
    const interval = window.setInterval(() => router.refresh(), 5_000);
    return () => window.clearInterval(interval);
  }, [active, router]);

  if (!active) return null;

  return (
    <section
      role="status"
      className="flex flex-col gap-4 rounded-2xl border border-[#9bc6b7] bg-[#e5f0ec] p-5 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <h2 className="font-semibold text-[#1f6b59]">{copy.title}</h2>
        <p className="mt-1 text-sm leading-6 text-[#53616a]">{copy.hint}</p>
      </div>
      <button
        type="button"
        onClick={() => router.refresh()}
        className="inline-flex shrink-0 justify-center rounded-full border border-[#1f6b59] px-4 py-2 text-sm font-semibold text-[#1f6b59] transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-[#1f6b59] focus:ring-offset-2"
      >
        {copy.refresh}
      </button>
    </section>
  );
}

export function SearchRunHistory({
  runs,
  copy,
}: {
  runs: SearchRun[];
  copy: {
    title: string;
    hint: string;
    deleteAction: string;
    deleteConfirm: string;
    deleteError: string;
    status: Record<SearchRunStatus, string>;
  };
}) {
  const router = useRouter();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (runs.length === 0) return null;

  async function deleteRun(runId: string) {
    if (!window.confirm(copy.deleteConfirm)) return;
    setDeletingId(runId);
    setError(null);
    try {
      const response = await fetch(`/api/search-runs/${runId}`, { method: "DELETE" });
      if (!response.ok) throw new Error("delete failed");
      router.refresh();
    } catch {
      setError(copy.deleteError);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6 shadow-[0_12px_40px_rgba(21,33,43,0.05)] sm:p-8">
      <div className="flex flex-col gap-2 border-b border-[#ece9e2] pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">{copy.title}</h2>
          <p className="mt-1 text-sm leading-6 text-[#6d787e]">{copy.hint}</p>
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-4 rounded-xl border border-[#e8b4a4] bg-[#fff0eb] px-4 py-3 text-sm text-[#9b351c]">
          {error}
        </p>
      )}
      <ul className="mt-5 divide-y divide-[#ece9e2]">
        {runs.map((run) => {
          const canDelete = terminalStatuses.has(run.status);
          return (
            <li key={run.id} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-mono text-sm text-[#15212b]">{run.id.slice(0, 8)}</p>
                <p className="mt-1 text-xs text-[#6d787e]">
                  {run.created_at.slice(0, 10)} · {copy.status[run.status] ?? run.status} · {run.trigger}
                </p>
              </div>
              {canDelete && (
                <button
                  type="button"
                  onClick={() => deleteRun(run.id)}
                  disabled={deletingId === run.id}
                  className="inline-flex justify-center rounded-full border border-[#d9a295] px-4 py-2 text-sm font-semibold text-[#9b351c] transition hover:bg-[#fff0eb] focus:outline-none focus:ring-2 focus:ring-[#d9623c] focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
                >
                  {deletingId === run.id ? "…" : copy.deleteAction}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
