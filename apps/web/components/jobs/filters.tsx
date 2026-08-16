"use client";

import type { MatchFilters } from "@/lib/jobs/filter";

const selectClass =
  "rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-3 py-2 text-sm font-normal outline-none transition focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]";

export function MatchFiltersBar({
  filters,
  onChange,
}: {
  filters: MatchFilters;
  onChange: (filters: MatchFilters) => void;
}) {
  function update<K extends keyof MatchFilters>(key: K, value: MatchFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  const active =
    filters.region !== "all" ||
    filters.workMode !== "all" ||
    filters.status !== "all" ||
    filters.minScore > 0 ||
    filters.dateFrom !== null ||
    filters.dateTo !== null;

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-2xl border border-[#d9d5cc] bg-white p-4"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="flex flex-col gap-1.5 text-xs font-semibold text-[#53616a]">
        Region
        <select
          value={filters.region}
          onChange={(event) => update("region", event.target.value as MatchFilters["region"])}
          className={selectClass}
        >
          <option value="all">All regions</option>
          <option value="indonesia">Indonesia</option>
          <option value="global">Global</option>
        </select>
      </label>
      <label className="flex flex-col gap-1.5 text-xs font-semibold text-[#53616a]">
        Work mode
        <select
          value={filters.workMode}
          onChange={(event) => update("workMode", event.target.value as MatchFilters["workMode"])}
          className={selectClass}
        >
          <option value="all">All modes</option>
          <option value="on-site">On-site</option>
          <option value="hybrid">Hybrid</option>
          <option value="remote">Remote</option>
        </select>
      </label>
      <label className="flex flex-col gap-1.5 text-xs font-semibold text-[#53616a]">
        Status
        <select
          value={filters.status}
          onChange={(event) => update("status", event.target.value as MatchFilters["status"])}
          className={selectClass}
        >
          <option value="all">All statuses</option>
          <option value="new">New</option>
          <option value="saved">Saved</option>
          <option value="applied">Applied</option>
          <option value="ignored">Ignored</option>
        </select>
      </label>
      <label className="flex flex-col gap-1.5 text-xs font-semibold text-[#53616a]">
        Min score
        <input
          type="number"
          min={0}
          max={100}
          value={filters.minScore === 0 ? "" : filters.minScore}
          onChange={(event) => {
            const value = event.target.value === "" ? 0 : Number(event.target.value);
            update("minScore", Number.isNaN(value) ? 0 : Math.max(0, Math.min(100, Math.round(value))));
          }}
          placeholder="0"
          className={`${selectClass} w-20`}
        />
      </label>
      {active && (
        <button
          type="button"
          onClick={() => onChange({ ...filters, region: "all", workMode: "all", status: "all", minScore: 0, dateFrom: null, dateTo: null })}
          className="rounded-full border border-[#d9d5cc] px-4 py-2 text-xs font-semibold text-[#53616a] transition hover:bg-[#f4f1ea]"
        >
          Clear filters
        </button>
      )}
    </form>
  );
}