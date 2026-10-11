"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ScoreBadge } from "@/components/jobs/score-badge";
import { MatchFiltersBar } from "@/components/jobs/filters";
import {
  applyMatchFilters,
  defaultMatchFilters,
  sortMatchesDefault,
  type MatchFilters,
  type MatchRow,
} from "@/lib/jobs/filter";

type SortKey = "overallScore" | "title" | "company" | "publishedAt";

type SortState = { key: SortKey; direction: "asc" | "desc" };

const SORT_LABELS: Record<SortKey, string> = {
  overallScore: "Match",
  title: "Job title",
  company: "Company",
  publishedAt: "Published",
};

const INITIAL_VISIBLE_COUNT = 5;
function formatDate(value: string | null): string {
  if (!value) return "—";
  return value.slice(0, 10);
}

function compareRows(a: MatchRow, b: MatchRow, state: SortState): number {
  let result: number;
  switch (state.key) {
    case "overallScore":
      result = a.overallScore - b.overallScore;
      break;
    case "publishedAt": {
      const aTime = a.publishedAt ? new Date(a.publishedAt).getTime() : -Infinity;
      const bTime = b.publishedAt ? new Date(b.publishedAt).getTime() : -Infinity;
      result = aTime - bTime;
      break;
    }
    default:
      result = (a[state.key] ?? "").localeCompare(b[state.key] ?? "");
  }
  return state.direction === "asc" ? result : -result;
}

export function MatchTable({
  rows,
  emptyMessage = "No matches match the current filters.",
}: {
  rows: MatchRow[];
  emptyMessage?: string;
}) {
  const [filters, setFilters] = useState<MatchFilters>(() => defaultMatchFilters());
  const [sort, setSort] = useState<SortState>({ key: "overallScore", direction: "desc" });
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_COUNT);
  const [statuses, setStatuses] = useState<Record<string, MatchRow["status"]>>(() =>
    Object.fromEntries(rows.map((row) => [row.jobId, row.status])),
  );
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [removedJobIds, setRemovedJobIds] = useState<Set<string>>(() => new Set());

  const visibleRows = useMemo(() => {
    const filtered = applyMatchFilters(rows, filters).filter((row) => {
      const currentStatus = statuses[row.jobId] ?? row.status;
      if (removedJobIds.has(row.jobId)) return false;
      if (filters.status === "all" && currentStatus === "ignored") return false;
      return true;
    });
    if (sort.key === "overallScore" && sort.direction === "desc") {
      return sortMatchesDefault(filtered);
    }
    return filtered
      .map((row) => ({ ...row, status: statuses[row.jobId] ?? row.status }))
      .sort((a, b) => compareRows(a, b, sort));
  }, [rows, filters, sort, statuses, removedJobIds]);

  const displayedRows = visibleRows.slice(0, visibleCount);
  function toggleSort(key: SortKey) {
    setSort((current) => {
      if (current.key === key) {
        return { key, direction: current.direction === "desc" ? "asc" : "desc" };
      }
      return { key, direction: key === "overallScore" ? "desc" : "asc" };
    });
  }

  async function setStatus(jobId: string, status: MatchRow["status"]) {
    setSaving((current) => ({ ...current, [jobId]: true }));
    const previous = statuses[jobId] ?? "new";
    setStatuses((current) => ({ ...current, [jobId]: status }));
    try {
      const response = await fetch("/api/job-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, status }),
      });
      if (!response.ok) {
        setStatuses((current) => ({ ...current, [jobId]: previous }));
      }
    } catch {
      setStatuses((current) => ({ ...current, [jobId]: previous }));
    } finally {
      setSaving((current) => ({ ...current, [jobId]: false }));
    }
  }

  async function removeJob(jobId: string) {
    setRemovedJobIds((prev) => {
      const next = new Set(prev);
      next.add(jobId);
      return next;
    });
    setSaving((current) => ({ ...current, [jobId]: true }));
    try {
      await fetch(`/api/job-status?job_id=${encodeURIComponent(jobId)}`, {
        method: "DELETE",
      });
    } catch {
      // Best-effort permanent removal
    } finally {
      setSaving((current) => ({ ...current, [jobId]: false }));
    }
  }

  return (
    <div className="space-y-4">
      <MatchFiltersBar filters={filters} onChange={setFilters} />
      <div className="overflow-x-auto overflow-y-auto max-h-[75vh] rounded-2xl border border-[#d9d5cc] bg-white">
        <table className="w-full min-w-[800px] text-left text-sm">
          <caption className="sr-only">Ranked job matches</caption>
          <thead className="sticky top-0 z-10 bg-white">
            <tr className="border-b border-[#d9d5cc] text-xs uppercase tracking-[0.14em] text-[#6d787e] bg-white">
              {(["title", "company", "publishedAt", "overallScore"] as SortKey[]).map((key) => (
                <th
                  key={key}
                  scope="col"
                  aria-sort={sort.key === key ? (sort.direction === "desc" ? "descending" : "ascending") : "none"}
                  className="sticky top-0 z-10 bg-white px-4 py-3 font-semibold shadow-[inset_0_-1px_0_0_#d9d5cc]"
                >
                  <button
                    type="button"
                    onClick={() => toggleSort(key)}
                    className="inline-flex items-center gap-1 uppercase tracking-[0.14em] transition hover:text-[#d9623c]"
                  >
                    {SORT_LABELS[key]}
                    {sort.key === key && <span aria-hidden="true">{sort.direction === "desc" ? "↓" : "↑"}</span>}
                  </button>
                </th>
              ))}
              <th scope="col" className="sticky top-0 z-10 bg-white px-4 py-3 font-semibold shadow-[inset_0_-1px_0_0_#d9d5cc]">
                Location
              </th>
              <th scope="col" className="sticky top-0 z-10 bg-white px-4 py-3 text-right font-semibold shadow-[inset_0_-1px_0_0_#d9d5cc]">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {displayedRows.map((row) => {
              const status = statuses[row.jobId] ?? row.status;
              return (
                <tr key={row.matchId} className="border-b border-[#ece9e2] last:border-0 hover:bg-[#faf9f6]">
                  <td className="max-w-64 px-4 py-3">
                    <Link
                      href={`/jobs/${row.matchId}`}
                      className="font-semibold text-[#15212b] transition hover:text-[#d9623c]"
                    >
                      {row.title}
                    </Link>
                    <span className="mt-1 block text-xs text-[#6d787e]">{row.employmentType ?? "—"}</span>
                  </td>
                  <td className="px-4 py-3 text-[#53616a]">{row.company}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[#6d787e]">
                    {formatDate(row.publishedAt)}
                  </td>
                  <td className="px-4 py-3">
                    <ScoreBadge score={row.overallScore} />
                  </td>
                  <td className="px-4 py-3 text-[#53616a]">{row.location ?? "—"}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <div className="inline-flex items-center gap-2">
                      <button
                        type="button"
                        disabled={saving[row.jobId]}
                        onClick={() => setStatus(row.jobId, status === "saved" ? "new" : "saved")}
                        className="rounded-full bg-[#15212b] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-[#263946] disabled:opacity-60"
                      >
                        {status === "saved" ? "Unsave" : "Save"}
                      </button>
                      <button
                        type="button"
                        disabled={saving[row.jobId]}
                        onClick={() => removeJob(row.jobId)}
                        className="rounded-full border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-50 hover:border-rose-300 disabled:opacity-60"
                        title="Remove job from search results"
                      >
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {visibleRows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-sm text-[#6d787e]">
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {visibleRows.length > INITIAL_VISIBLE_COUNT && (
        <div className="flex items-center justify-center pt-2">
          {visibleCount < visibleRows.length ? (
            <button
              type="button"
              onClick={() => setVisibleCount((prev) => prev + 5)}
              className="inline-flex items-center gap-2 rounded-full border border-[#d9d5cc] bg-white px-5 py-2.5 text-xs font-semibold text-[#15212b] shadow-xs transition hover:bg-[#faf9f6] hover:border-[#15212b]"
            >
              Show more ({visibleRows.length - visibleCount} more)
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setVisibleCount(INITIAL_VISIBLE_COUNT)}
              className="inline-flex items-center gap-2 rounded-full border border-[#d9d5cc] bg-white px-5 py-2.5 text-xs font-semibold text-[#53616a] shadow-xs transition hover:bg-[#faf9f6]"
            >
              Show less
            </button>
          )}
        </div>
      )}
    </div>
  );
}
