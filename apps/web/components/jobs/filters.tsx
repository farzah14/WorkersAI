"use client";

import { useTranslations } from "next-intl";
import { EMPLOYMENT_TYPES } from "@/lib/search/schema";
import type { MatchFilters, WorkModeValue } from "@/lib/jobs/filter";

const selectClass =
  "rounded-xl border border-[#c9c7c0] bg-[#faf9f6] pl-3.5 pr-8 py-2 text-sm font-normal outline-none transition focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]";

const inputClass =
  "rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-3 py-2 text-sm font-normal outline-none transition focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]";

const labelClass = "flex flex-col gap-1.5 text-xs font-semibold text-[#53616a]";

export function MatchFiltersBar({
  filters,
  onChange,
  onClear,
  sources,
  dateDraft,
  dateError,
  onDateChange,
  shownCount,
  totalCount,
}: {
  filters: MatchFilters;
  onChange: (filters: MatchFilters) => void;
  onClear: () => void;
  sources: string[];
  dateDraft: { from: string; to: string };
  dateError: boolean;
  onDateChange: (draft: { from: string; to: string }) => void;
  shownCount: number;
  totalCount: number;
}) {
  const t = useTranslations("jobFilters");

  function update<K extends keyof MatchFilters>(key: K, value: MatchFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  const active =
    filters.query !== "" ||
    filters.region !== "all" ||
    filters.workMode !== "all" ||
    filters.employmentType !== "all" ||
    filters.sourceName !== null ||
    filters.status !== "all" ||
    filters.minScore > 0 ||
    filters.dateFrom !== null ||
    filters.dateTo !== null;

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => event.preventDefault()}
      aria-label={t("formLabel")}
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className={`${labelClass} min-w-56 flex-1`}>
          {t("query")}
          <input
            type="search"
            value={filters.query}
            onChange={(event) => update("query", event.target.value)}
            placeholder={t("queryPlaceholder")}
            maxLength={200}
            className={inputClass}
          />
        </label>
        <label className={labelClass}>
          {t("region")}
          <select
            value={filters.region}
            onChange={(event) => update("region", event.target.value as MatchFilters["region"])}
            className={selectClass}
          >
            <option value="all">{t("allRegions")}</option>
            <option value="indonesia">{t("indonesia")}</option>
            <option value="global">{t("global")}</option>
          </select>
        </label>
        <label className={labelClass}>
          {t("workMode")}
          <select
            value={filters.workMode}
            onChange={(event) => update("workMode", event.target.value as MatchFilters["workMode"])}
            className={selectClass}
          >
            <option value="all">{t("allWorkModes")}</option>
            {(["remote", "hybrid", "on-site"] as WorkModeValue[]).map((mode) => (
              <option key={mode} value={mode}>
                {t(mode === "on-site" ? "onSite" : mode)}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          {t("employmentType")}
          <select
            value={filters.employmentType}
            onChange={(event) =>
              update("employmentType", event.target.value as MatchFilters["employmentType"])
            }
            className={selectClass}
          >
            <option value="all">{t("allEmploymentTypes")}</option>
            {EMPLOYMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(type)}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          {t("source")}
          <select
            value={filters.sourceName ?? ""}
            onChange={(event) =>
              update("sourceName", event.target.value === "" ? null : event.target.value)
            }
            className={selectClass}
          >
            <option value="">{t("allSources")}</option>
            {sources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          {t("status")}
          <select
            value={filters.status}
            onChange={(event) => update("status", event.target.value as MatchFilters["status"])}
            className={selectClass}
          >
            <option value="all">{t("allStatuses")}</option>
            <option value="new">{t("new")}</option>
            <option value="saved">{t("saved")}</option>
            <option value="applied">{t("applied")}</option>
            <option value="ignored">{t("ignored")}</option>
          </select>
        </label>
        <label className={labelClass}>
          {t("minScore")}
          <input
            type="number"
            min={0}
            max={100}
            value={filters.minScore === 0 ? "" : filters.minScore}
            onChange={(event) => {
              const value = event.target.value === "" ? 0 : Number(event.target.value);
              update(
                "minScore",
                Number.isNaN(value) ? 0 : Math.max(0, Math.min(100, Math.round(value))),
              );
            }}
            placeholder="0"
            className={`${inputClass} w-20`}
          />
        </label>
        <label className={labelClass}>
          {t("dateFrom")}
          <input
            type="date"
            value={dateDraft.from}
            onChange={(event) => onDateChange({ ...dateDraft, from: event.target.value })}
            aria-invalid={dateError}
            aria-describedby={dateError ? "filter-date-error" : undefined}
            className={inputClass}
          />
        </label>
        <label className={labelClass}>
          {t("dateTo")}
          <input
            type="date"
            value={dateDraft.to}
            onChange={(event) => onDateChange({ ...dateDraft, to: event.target.value })}
            aria-invalid={dateError}
            aria-describedby={dateError ? "filter-date-error" : undefined}
            className={inputClass}
          />
        </label>
        {active && (
          <button
            type="button"
            onClick={onClear}
            className="rounded-full border border-[#d9d5cc] px-4 py-2 text-xs font-semibold text-[#53616a] transition hover:bg-[#f4f1ea]"
          >
            {t("clear")}
          </button>
        )}
      </div>

      <div className="flex flex-col gap-1 text-xs text-[#6d787e]">
        <p role="status" aria-live="polite">
          {t("filteredCount", { shown: shownCount, total: totalCount })}
        </p>
        <p>{t("unknownMetadataHint")}</p>
        {dateError && (
          <p id="filter-date-error" role="alert" className="font-semibold text-rose-700">
            {t("invalidDateRange")}
          </p>
        )}
      </div>
    </form>
  );
}
