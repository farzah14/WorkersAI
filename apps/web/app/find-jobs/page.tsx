"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-5xl animate-pulse space-y-5">
        <div className="h-5 w-32 rounded-full bg-[#d9d5cc]" />
        <div className="h-16 max-w-xl rounded bg-[#e5e1d8]" />
        <div className="h-96 rounded-2xl bg-white/70" />
      </div>
    </main>
  );
}

function EmptyState({ state }: { state: Exclude<LoadState, "loading" | "ready"> }) {
  const content: Record<Exclude<LoadState, "loading" | "ready">, { title: string; body: string; href: string; link: string }> = {
    unauthorized: {
      title: "Sign in to find your next role",
      body: "Your search preferences are private and tied to your account.",
      href: "/login",
      link: "Sign in",
    },
    "missing-cv": {
      title: "Start with an active CV",
      body: "Upload a digital PDF or DOCX CV, then set it as active before configuring a search.",
      href: "/cvs",
      link: "Open My CVs",
    },
    unconfirmed: {
      title: "Confirm your candidate profile first",
      body: "Review the extracted profile and confirm it before we use it to discover jobs.",
      href: "/onboarding/profile",
      link: "Review candidate profile",
    },
    error: {
      title: "Search preferences are unavailable",
      body: "We could not load the active CV and candidate profile. Refresh the page and try again.",
      href: "/find-jobs",
      link: "Try again",
    },
  };
  const current = content[state];

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-16 text-[#15212b] sm:px-8">
      <section className="mx-auto max-w-xl rounded-3xl border border-[#d9d5cc] bg-white p-8 shadow-[0_20px_60px_rgba(21,33,43,0.08)] sm:p-12">
        <p className="mb-5 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">Find jobs</p>
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
  );
}

export default function FindJobsPage() {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [values, setValues] = useState<FormValues | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

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
        region: "indonesia",
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
  }, []);

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
    setRunId(null);

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

      if (data?.run_id) setRunId(data.run_id);
    } catch {
      setError("The search could not be started. Check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-8 text-[#15212b] sm:px-8 sm:py-12">
      <div className="mx-auto max-w-5xl">
        <header className="grid gap-8 border-b border-[#d9d5cc] pb-10 lg:grid-cols-[1fr_280px] lg:items-end">
          <div>
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">Search profile</p>
            <h1 className="max-w-2xl text-4xl font-semibold tracking-[-0.06em] sm:text-6xl">
              Find work that fits the person behind your CV.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-[#53616a]">
              Tune the brief before discovery starts. Your confirmed candidate profile stays the source of truth.
            </p>
          </div>
          <aside className="border-l-2 border-[#d9623c] pl-5 text-sm leading-6 text-[#53616a]">
            <p className="font-semibold text-[#15212b]">Active CV</p>
            <p className="mt-1 break-words">{values.cvName}</p>
            <p className="mt-4 font-semibold text-[#15212b]">Profile signal</p>
            <p className="mt-1 capitalize">{values.seniority} seniority</p>
          </aside>
        </header>

        <form onSubmit={submitSearch} className="mt-10 space-y-8">
          <section className="rounded-3xl bg-[#15212b] p-6 text-white shadow-[0_20px_60px_rgba(21,33,43,0.16)] sm:p-8">
            <fieldset>
              <legend className="text-lg font-semibold">Where should we look?</legend>
              <p className="mt-2 max-w-xl text-sm leading-6 text-[#b9c5c9]">
                Choose one region. This changes the discovery sources and query language used by the worker.
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
              Target roles
              <input
                value={values.targetRoles}
                onChange={(event) => updateValue("targetRoles", event.target.value)}
                placeholder="Data Engineer, Analytics Engineer"
                required
                className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
              />
              <span className="font-normal text-xs text-[#6d787e]">Separate multiple roles with commas.</span>
            </label>

            <label className="flex flex-col gap-2 text-sm font-semibold">
              Locations
              <input
                value={values.locations}
                onChange={(event) => updateValue("locations", event.target.value)}
                placeholder="Jakarta, Bandung, or leave broad"
                className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
              />
            </label>

            <fieldset>
              <legend className="text-sm font-semibold">Work modes</legend>
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
              <p className="mt-2 text-xs font-normal text-[#6d787e]">Leave blank to keep all modes in scope.</p>
            </fieldset>

            <fieldset className="lg:col-span-2">
              <legend className="text-sm font-semibold">Employment types</legend>
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
              <p className="text-sm font-semibold">Compensation floor</p>
              <p className="mt-2 text-sm leading-6 text-[#6d787e]">Optional. Jobs without salary data may still appear.</p>
            </div>
            <div className="grid grid-cols-[1fr_110px] gap-3">
              <label className="flex flex-col gap-2 text-sm font-semibold">
                Minimum salary
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
                Currency
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
              Excluded keywords
              <input
                value={values.excludedKeywords}
                onChange={(event) => updateValue("excludedKeywords", event.target.value)}
                placeholder="Sales, commission, unpaid"
                className="rounded-xl border border-[#c9c7c0] bg-[#faf9f6] px-4 py-3 font-normal outline-none transition placeholder:text-[#8b9599] focus:border-[#d9623c] focus:ring-2 focus:ring-[#f7c3b3]"
              />
              <span className="font-normal text-xs text-[#6d787e]">Separate keywords with commas.</span>
            </label>
          </section>

          <section className="flex flex-col gap-5 rounded-3xl border border-[#d9d5cc] bg-[#e5f0ec] p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
            <div>
              <p className="text-sm font-semibold">Keep this search running</p>
              <p className="mt-2 max-w-xl text-sm leading-6 text-[#53616a]">
                Turn on daily discovery to refresh results using these preferences and your active CV.
              </p>
            </div>
            <label className="inline-flex shrink-0 cursor-pointer items-center gap-3 text-sm font-semibold">
              <input
                type="checkbox"
                checked={values.dailyEnabled}
                onChange={(event) => updateValue("dailyEnabled", event.target.checked)}
                className="h-5 w-5 rounded border-[#8ba59b] accent-[#1f6b59] focus:ring-2 focus:ring-[#1f6b59]"
              />
              Enable daily search
            </label>
          </section>

          {error && (
            <p role="alert" className="rounded-xl border border-[#e8b4a4] bg-[#fff0eb] px-4 py-3 text-sm text-[#9b351c]">
              {error}
            </p>
          )}
          {runId && (
            <p role="status" className="rounded-xl border border-[#9bc6b7] bg-[#e5f0ec] px-4 py-3 text-sm text-[#1f6b59]">
              Search queued. Run <span className="font-mono">{runId}</span> is ready for discovery.
            </p>
          )}

          <div className="flex flex-col gap-4 border-t border-[#d9d5cc] pt-8 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-[#6d787e]">You can adjust this brief each time you search.</p>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex justify-center rounded-full bg-[#d9623c] px-7 py-3.5 text-sm font-semibold text-white shadow-[0_10px_20px_rgba(217,98,60,0.22)] transition hover:bg-[#bb4f2e] focus:outline-none focus:ring-2 focus:ring-[#d9623c] focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
            >
              {submitting ? "Starting search..." : "Find Jobs Now"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}
