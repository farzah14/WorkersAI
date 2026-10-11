"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { candidateProfileSchema } from "@/lib/profile/schema";
import { createClient } from "@/lib/supabase/client";
import {
  EMPLOYMENT_TYPES,
  REGIONS,
  searchProfileSchema,
  WORK_MODES,
} from "@/lib/search/schema";

type Region = (typeof REGIONS)[number];
type WorkMode = (typeof WORK_MODES)[number];
type EmploymentType = (typeof EMPLOYMENT_TYPES)[number];

type LoadState = "loading" | "ready" | "unauthorized" | "missing-cv" | "unconfirmed" | "error";

type FormValues = {
  candidateProfileId: string;
  cvName: string;
  seniority: string;
  region: Region;
  targetRoles: string;
  locations: string;
  workModes: WorkMode[];
  employmentTypes: EmploymentType[];
  minSalary: string;
  salaryCurrency: string;
  excludedKeywords: string;
  dailyEnabled: boolean;
};

const regionLabels: Record<Region, string> = {
  indonesia: "Indonesia",
  global: "Global",
};

const workModeLabels: Record<WorkMode, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  "on-site": "On-site",
};

const employmentTypeLabels: Record<EmploymentType, string> = {
  "full-time": "Full-time",
  "part-time": "Part-time",
  contract: "Contract",
  temporary: "Temporary",
  internship: "Internship",
  apprenticeship: "Apprenticeship",
  volunteer: "Volunteer",
  freelance: "Freelance",
};

function listToArray(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toggleValue<T extends string>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function seniorityEmploymentDefaults(seniority: string): EmploymentType[] {
  return seniority === "intern" ? ["internship"] : ["full-time"];
}

function LoadingState() {
  return (
    <DashboardShell>
      <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
        <div className="mx-auto max-w-5xl animate-pulse space-y-5">
          <div className="h-5 w-32 rounded-full bg-[#d9d5cc]" />
          <div className="h-16 max-w-xl rounded bg-[#e5e1d8]" />
          <div className="h-96 rounded-2xl bg-white/70" />
        </div>
      </main>
    </DashboardShell>
  );
}

function EmptyState({ state }: { state: Exclude<LoadState, "loading" | "ready"> }) {
  const t = useTranslations("findJobs");
  const content: Record<Exclude<LoadState, "loading" | "ready">, { title: string; body: string; href: string; link: string }> = {
    unauthorized: {
      title: t("empty.unauthorizedTitle"),
      body: t("empty.unauthorizedBody"),
      href: "/login",
      link: t("empty.unauthorizedLink"),
    },
    "missing-cv": {
      title: t("empty.missingCvTitle"),
      body: t("empty.missingCvBody"),
      href: "/dashboard/profile",
      link: t("empty.missingCvLink"),
    },
    unconfirmed: {
      title: t("empty.unconfirmedTitle"),
      body: t("empty.unconfirmedBody"),
      href: "/onboarding/profile",
      link: t("empty.unconfirmedLink"),
    },
    error: {
      title: t("empty.errorTitle"),
      body: t("empty.errorBody"),
      href: "/find-jobs",
      link: t("empty.errorLink"),
    },
  };
  const current = content[state];

  return (
    <DashboardShell>
      <main className="min-h-screen bg-[#f4f1ea] px-5 py-16 text-[#15212b] sm:px-8">
        <section className="mx-auto max-w-xl rounded-3xl border border-[#d9d5cc] bg-white p-8 shadow-[0_20px_60px_rgba(21,33,43,0.08)] sm:p-12">
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">{t("empty.tag")}</p>
          <h1 className="max-w-md text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">{current.title}</h1>
          <p className="mt-4 leading-7 text-[#53616a]">{current.body}</p>
          <Link
            href={current.href}
            className="mt-8 inline-flex rounded-full bg-[#15212b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#263946] focus:outline-none focus:ring-2 focus:ring-[#d9623c] focus:ring-offset-2"
          >
            {current.link}
          </Link>
        </section>
      </main>
    </DashboardShell>
  );
}

function FindJobsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useTranslations("findJobs");
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [values, setValues] = useState<FormValues | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSearchProfile() {
      const supabase = createClient();
      const {
        data: { user },
        error: authError,
      } = await supabase.auth.getUser();

      if (cancelled) return;
      if (authError || !user) {
        setLoadState("unauthorized");
        return;
      }

      const { data: activeCv, error: cvError } = await supabase
        .from("cvs")
        .select("id, original_name")
        .eq("user_id", user.id)
        .eq("is_active", true)
        .maybeSingle();

      if (cancelled) return;
      if (cvError) {
        setLoadState("error");
        return;
      }
      if (!activeCv) {
        setLoadState("missing-cv");
        return;
      }

      const { data: profileRow, error: profileError } = await supabase
        .from("candidate_profiles")
        .select("id, profile, version, confirmed_at")
        .eq("user_id", user.id)
        .eq("cv_id", activeCv.id)
        .not("confirmed_at", "is", null)
        .order("version", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (cancelled) return;
      if (profileError) {
        setLoadState("error");
        return;
      }
      if (!profileRow || !profileRow.confirmed_at) {
        setLoadState("unconfirmed");
        return;
      }

      const profile = candidateProfileSchema.safeParse(profileRow.profile);
      if (!profile.success) {
        setLoadState("error");
        return;
      }

      setValues({
        candidateProfileId: profileRow.id,
        cvName: activeCv.original_name,
        seniority: profile.data.seniority,
        region: searchParams.get("region") === "global" ? "global" : "indonesia",
        targetRoles: profile.data.target_roles.join(", "),
        locations: "",
        workModes: [],
        employmentTypes: seniorityEmploymentDefaults(profile.data.seniority),
        minSalary: "",
        salaryCurrency: "",
        excludedKeywords: "",
        dailyEnabled: false,
      });
      setLoadState("ready");
    }

    void loadSearchProfile();
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  if (loadState === "loading") return <LoadingState />;
  if (loadState !== "ready") return <EmptyState state={loadState} />;
  if (!values) return <EmptyState state="error" />;
  const currentValues = values;

  function updateValue<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setValues((current) => (current ? { ...current, [key]: value } : current));
  }

  async function submitSearch(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    const parsed = searchProfileSchema.safeParse({
      candidate_profile_id: currentValues.candidateProfileId,
      region: currentValues.region,
      target_roles: listToArray(currentValues.targetRoles),
      locations: listToArray(currentValues.locations),
      work_modes: currentValues.workModes,
      employment_types: currentValues.employmentTypes,
      min_salary: currentValues.minSalary === "" ? undefined : Number(currentValues.minSalary),
      salary_currency: currentValues.salaryCurrency,
      excluded_keywords: listToArray(currentValues.excludedKeywords),
      daily_enabled: currentValues.dailyEnabled,
    });

    if (!parsed.success) {
      setError("Add at least one target role and check the other search preferences.");
      setSubmitting(false);
      return;
    }

    try {
      const response = await fetch("/api/search-runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });
      const data = (await response.json().catch(() => null)) as { error?: string; run_id?: string } | null;

      if (!response.ok) {
        setError(
          data?.error === "confirmed_active_profile_required"
            ? "Your active CV needs a confirmed candidate profile. Review it before searching."
            : data?.error === "validation_failed"
              ? "Check the search preferences and try again."
              : data?.error ?? "Could not start the job search.",
        );
        return;
      }

      if (response.status !== 202 || !data?.run_id) {
        setError("Could not start the job search.");
        return;
      }

      router.push("/dashboard");
    } catch {
      setError(t("searchFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DashboardShell>
      <main className="min-h-screen bg-[#f4f1ea] px-5 py-8 text-[#15212b] sm:px-8 sm:py-12">
        <div className="mx-auto max-w-5xl">
        <header className="grid gap-8 border-b border-[#d9d5cc] pb-10 lg:grid-cols-[1fr_280px] lg:items-end">
          <div>
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">{t("tag")}</p>
            <h1 className="max-w-2xl text-4xl font-semibold tracking-[-0.06em] sm:text-6xl">
              {t("title")}
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-[#53616a]">
              {t("subheading")}
            </p>
          </div>
          <aside className="border-l-2 border-[#d9623c] pl-5 text-sm leading-6 text-[#53616a]">
            <p className="font-semibold text-[#15212b]">{t("activeCv")}</p>
            <p className="mt-1 break-words">{values.cvName}</p>
            <p className="mt-4 font-semibold text-[#15212b]">{t("profileSignal")}</p>
            <p className="mt-1 capitalize">{t("seniorityLevel", { seniority: values.seniority })}</p>
          </aside>
        </header>

        <form onSubmit={submitSearch} className="mt-10 space-y-8">
          <section className="rounded-3xl bg-[#15212b] p-6 text-white shadow-[0_20px_60px_rgba(21,33,43,0.16)] sm:p-8">
            <fieldset>
              <legend className="text-lg font-semibold">{t("regionLegend")}</legend>
              <p className="mt-2 max-w-xl text-sm leading-6 text-[#b9c5c9]">
                {t("regionHint")}
              </p>
              <div className="mt-6 grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Search region">
                {REGIONS.map((region) => (
                  <label key={region} className="cursor-pointer">
                    <input
                      type="radio"
                      name="region"
                      value={region}
                      checked={values.region === region}
                      onChange={() => updateValue("region", region)}
                      className="peer sr-only"
                    />
                    <span className="flex items-center justify-between rounded-2xl border border-[#40505a] px-5 py-4 text-sm font-semibold transition peer-checked:border-[#f28b68] peer-checked:bg-[#d9623c] peer-focus-visible:ring-2 peer-focus-visible:ring-[#f28b68]">
                      {regionLabels[region]}
                      <span
                        aria-hidden="true"
                        className={`h-2.5 w-2.5 rounded-full ${values.region === region ? "bg-[#f7c3b3]" : "border border-[#80919a]"}`}
                      />
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          </section>

          <section className="grid gap-6 rounded-3xl border border-[#d9d5cc] bg-white p-6 shadow-[0_12px_40px_rgba(21,33,43,0.05)] sm:p-8 lg:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm font-semibold lg:col-span-2">
              {t("targetRoles")}
              <input
                value={values.targetRoles}
                onChange={(event) => updateValue("targetRoles", event.target.value)}
                placeholder={t("targetRolesPlaceholder")}
                required
                className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
              />
              <span className="font-normal text-xs text-[#6d787e]">{t("targetRolesHint")}</span>
            </label>

            <label className="flex flex-col gap-2 text-sm font-semibold">
              {t("locations")}
              <input
                value={values.locations}
                onChange={(event) => updateValue("locations", event.target.value)}
                placeholder={t("locationsPlaceholder")}
                className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
              />
            </label>

            <fieldset>
              <legend className="text-sm font-semibold">{t("workModes")}</legend>
              <div className="mt-3 flex flex-wrap gap-2">
                {WORK_MODES.map((mode) => (
                  <label key={mode} className="cursor-pointer">
                    <input
                      type="checkbox"
                      checked={values.workModes.includes(mode)}
                      onChange={() => updateValue("workModes", toggleValue(values.workModes, mode))}
                      className="peer sr-only"
                    />
                    <span className="inline-flex rounded-full border border-[#c9c7c0] px-4 py-2 text-sm font-normal transition peer-checked:border-[#d9623c] peer-checked:bg-[#fff0eb] peer-checked:text-[#a33c1d] peer-focus-visible:ring-2 peer-focus-visible:ring-[#d9623c]">
                      {workModeLabels[mode]}
                    </span>
                  </label>
                ))}
              </div>
              <p className="mt-2 text-xs font-normal text-[#6d787e]">{t("workModesHint")}</p>
            </fieldset>

            <fieldset className="lg:col-span-2">
              <legend className="text-sm font-semibold">{t("employmentTypes")}</legend>
              <div className="mt-3 flex flex-wrap gap-2">
                {EMPLOYMENT_TYPES.map((type) => (
                  <label key={type} className="cursor-pointer">
                    <input
                      type="checkbox"
                      checked={values.employmentTypes.includes(type)}
                      onChange={() => updateValue("employmentTypes", toggleValue(values.employmentTypes, type))}
                      className="peer sr-only"
                    />
                    <span className="inline-flex rounded-full border border-[#c9c7c0] px-4 py-2 text-sm font-normal transition peer-checked:border-[#d9623c] peer-checked:bg-[#fff0eb] peer-checked:text-[#a33c1d] peer-focus-visible:ring-2 peer-focus-visible:ring-[#d9623c]">
                      {employmentTypeLabels[type]}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          </section>

          <section className="grid gap-6 rounded-3xl border border-[#d9d5cc] bg-white p-6 shadow-[0_12px_40px_rgba(21,33,43,0.05)] sm:p-8 lg:grid-cols-2">
            <div>
              <p className="text-sm font-semibold">{t("compensationFloor")}</p>
              <p className="mt-2 text-sm leading-6 text-[#6d787e]">{t("compensationHint")}</p>
            </div>
            <div className="grid grid-cols-[1fr_110px] gap-3">
              <label className="flex flex-col gap-2 text-sm font-semibold">
                {t("minSalary")}
                <input
                  type="number"
                  min="0"
                  value={values.minSalary}
                  onChange={(event) => updateValue("minSalary", event.target.value)}
                  placeholder="0"
                  className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-semibold">
                {t("currency")}
                <input
                  value={values.salaryCurrency}
                  onChange={(event) => updateValue("salaryCurrency", event.target.value)}
                  placeholder="IDR"
                  maxLength={8}
                  className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal uppercase outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
                />
              </label>
            </div>

            <label className="flex flex-col gap-2 text-sm font-semibold lg:col-span-2">
              {t("excludedKeywords")}
              <input
                value={values.excludedKeywords}
                onChange={(event) => updateValue("excludedKeywords", event.target.value)}
                placeholder={t("excludedKeywordsPlaceholder")}
                className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
              />
              <span className="font-normal text-xs text-[#6d787e]">{t("excludedKeywordsHint")}</span>
            </label>
          </section>

          <section className="flex flex-col gap-5 rounded-3xl border border-[#d9d5cc] bg-[#e5f0ec] p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
            <div>
              <p className="text-sm font-semibold">{t("dailyTitle")}</p>
              <p className="mt-2 max-w-xl text-sm leading-6 text-[#53616a]">
                {t("dailyHint")}
              </p>
            </div>
            <label className="inline-flex shrink-0 cursor-pointer items-center gap-3 text-sm font-semibold">
              <input
                type="checkbox"
                checked={values.dailyEnabled}
                onChange={(event) => updateValue("dailyEnabled", event.target.checked)}
                className="h-5 w-5 rounded border-[#8ba59b] accent-[#1f6b59] focus:ring-2 focus:ring-[#1f6b59]"
              />
              {t("dailyEnabled")}
            </label>
          </section>

          {error && (
            <p role="alert" className="rounded-xl border border-[#e8b4a4] bg-[#fff0eb] px-4 py-3 text-sm text-[#9b351c]">
              {error}
            </p>
          )}
          <div className="flex flex-col gap-4 border-t border-[#d9d5cc] pt-8 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-[#6d787e]">{t("briefNote")}</p>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex justify-center rounded-full bg-[#d9623c] px-7 py-3.5 text-sm font-semibold text-white shadow-[0_10px_20px_rgba(217,98,60,0.22)] transition hover:bg-[#bb4f2e] focus:outline-none focus:ring-2 focus:ring-[#d9623c] focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
            >
              {submitting ? t("submitting") : t("submitButton")}
            </button>
          </div>
        </form>
        </div>
      </main>
    </DashboardShell>
  );
}

export default function FindJobsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <FindJobsContent />
    </Suspense>
  );
}
