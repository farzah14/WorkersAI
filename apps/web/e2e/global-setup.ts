import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const SEED_EMAIL = "e2e@example.test";
const SEED_PASSWORD = "E2e-password-123";
const ISOLATION_EMAIL = "e2e-isolation@example.test";

type SeedState = {
  userId: string;
  runId: string;
  bestMatchId: string;
  bestJobUrl: string;
  otherUserId: string;
  otherUserMatchId: string;
  otherUserJobUrl: string;
  otherUserJobTitle: string;
};

function loadEnvFile(filePath: string): void {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
    for (const line of readFileSync(filePath, "utf8").split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const separator = trimmed.indexOf("=");
      const key = trimmed.slice(0, separator);
      const value = trimmed.slice(separator + 1).replace(/^["']|["']$/g, "");
      if (!process.env[key]) process.env[key] = value;
    }
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing environment variable ${name} for Playwright seed.`);
  return value;
}

async function upsertSeedUser(client: SupabaseClient, email: string): Promise<string> {
  const { data: { users } } = await client.auth.admin.listUsers({ perPage: 1000 });
  const existing = users?.find((user) => user.email === email);
  if (existing) return existing.id;

  const { data, error } = await client.auth.admin.createUser({
    email,
    password: SEED_PASSWORD,
    email_confirm: true,
  });
  if (error) throw error;
  return data.user.id;
}

async function resetUserData(client: SupabaseClient, userId: string): Promise<void> {
  const { data: runs } = await client
    .from("job_search_runs")
    .select("id")
    .eq("user_id", userId);
  const runIds = (runs ?? []).map((run) => run.id);

  if (runIds.length > 0) {
    await client.from("job_matches").delete().in("search_run_id", runIds);
    await client.from("user_jobs").delete().eq("user_id", userId);
    await client.from("exports").delete().eq("user_id", userId);
  }
  await client.from("job_search_runs").delete().eq("user_id", userId);
  await client.from("search_profiles").delete().eq("user_id", userId);
  await client.from("candidate_profiles").delete().eq("user_id", userId);
  await client.from("cvs").delete().eq("user_id", userId);
  await client.from("jobs").delete().like("fingerprint", "e2e-fp-%");
}

async function seedMatches(
  client: SupabaseClient,
  userId: string,
): Promise<Omit<SeedState, "otherUserId" | "otherUserMatchId" | "otherUserJobUrl" | "otherUserJobTitle">> {
  const { data: cv, error: cvError } = await client
    .from("cvs")
    .insert({
      user_id: userId,
      original_name: "e2e-cv.pdf",
      mime_type: "application/pdf",
      is_active: true,
      extraction_status: "extracted",
      retain_original: true,
    })
    .select("id")
    .single();
  if (cvError || !cv) throw cvError ?? new Error("cv insert failed");

  const profile = {
    name: "E2E Candidate",
    current_role: "Data Engineer",
    seniority: "mid",
    target_roles: ["Data Engineer"],
    skills: ["SQL", "Python", "Airflow"],
    experience_years: 5,
    languages: ["English"],
    education: ["Bachelor"],
  };
  const { data: candidate, error: candidateError } = await client
    .from("candidate_profiles")
    .insert({
      user_id: userId,
      cv_id: cv.id,
      version: 1,
      profile,
      confirmed_at: new Date().toISOString(),
    })
    .select("id")
    .single();
  if (candidateError || !candidate) throw candidateError ?? new Error("candidate profile insert failed");

  const { data: searchProfile, error: searchError } = await client
    .from("search_profiles")
    .insert({
      user_id: userId,
      candidate_profile_id: candidate.id,
      region: "indonesia",
      target_roles: ["Data Engineer"],
    })
    .select("id")
    .single();
  if (searchError || !searchProfile) throw searchError ?? new Error("search profile insert failed");

  const { data: run, error: runError } = await client
    .from("job_search_runs")
    .insert({
      user_id: userId,
      search_profile_id: searchProfile.id,
      candidate_profile_id: candidate.id,
      trigger: "manual",
      status: "completed",
      discovered_count: 4,
      normalized_count: 4,
      completed_at: new Date().toISOString(),
    })
    .select("id")
    .single();
  if (runError || !run) throw runError ?? new Error("search run insert failed");

  const today = new Date().toISOString();
  const jobs = [
    {
      fingerprint: "e2e-fp-best",
      title: "Data Engineer (Airflow)",
      company: "Acme Data",
      description: "Build data pipelines with Airflow and SQL.",
      source_name: "e2e",
      original_url: "https://example.test/jobs/best",
      canonical_url: "https://example.test/jobs/best",
      region: "indonesia",
      work_mode: "remote",
      employment_type: "full-time",
      published_at: today,
      status: "active",
    },
    {
      fingerprint: "e2e-fp-strong",
      title: "Senior Data Analyst",
      company: "Beta Labs",
      description: "Analyze product metrics with SQL and Python.",
      source_name: "e2e",
      original_url: "https://example.test/jobs/strong",
      canonical_url: "https://example.test/jobs/strong",
      region: "indonesia",
      work_mode: "hybrid",
      employment_type: "full-time",
      published_at: "2026-08-01T09:00:00Z",
      status: "active",
    },
    {
      fingerprint: "e2e-fp-potential",
      title: "BI Developer",
      company: "Gamma Retail",
      description: "Build dashboards for retail analytics.",
      source_name: "e2e",
      original_url: "https://example.test/jobs/potential",
      canonical_url: "https://example.test/jobs/potential",
      region: "indonesia",
      work_mode: "on-site",
      employment_type: "full-time",
      published_at: "2026-07-15T09:00:00Z",
      status: "active",
    },
    {
      fingerprint: "e2e-fp-low",
      title: "Receptionist",
      company: "Gamma Retail",
      description: "Welcome guests and manage the front desk.",
      source_name: "e2e",
      original_url: "https://example.test/jobs/low",
      canonical_url: "https://example.test/jobs/low",
      region: "indonesia",
      work_mode: "on-site",
      employment_type: "full-time",
      published_at: "2026-06-01T09:00:00Z",
      status: "active",
    },
  ];

  const insertedJobs: Array<{ id: string }> = [];
  for (const job of jobs) {
    const { data: row, error } = await client
      .from("jobs")
      .upsert(job, { onConflict: "fingerprint" })
      .select("id")
      .single();
    if (error || !row) throw error ?? new Error("job upsert failed");
    insertedJobs.push(row);
  }

  const specs = [
    {
      jobIndex: 0,
      overall: 92,
      verdict: "highly_recommended",
      explanation:
        "Your pipeline engineering background with Airflow and SQL matches the core of this role.",
      dimensions: [92, 94, 90, 85, 88, 96],
      strengths: ["SQL", "Python", "Airflow"],
      gaps: ["dbt"],
      critical: [],
      recommendations: ["Highlight your Airflow DAG design experience."],
    },
    {
      jobIndex: 1,
      overall: 85,
      verdict: "recommended",
      explanation: "Your SQL and Python skills align with the analytical requirements.",
      dimensions: [88, 90, 85, 80, 82, 84],
      strengths: ["SQL", "Python"],
      gaps: ["Looker"],
      critical: [],
      recommendations: ["Add a project example using Looker."],
    },
    {
      jobIndex: 2,
      overall: 74,
      verdict: "potential",
      explanation: "Some dashboard tooling experience is missing but fundamentals are present.",
      dimensions: [70, 80, 75, 72, 76, 71],
      strengths: ["SQL"],
      gaps: ["Power BI", "Tableau"],
      critical: [],
      recommendations: ["Document any reporting work from previous roles."],
    },
    {
      jobIndex: 3,
      overall: 55,
      verdict: "low_match",
      explanation: "The role requires front-office experience not present in the profile.",
      dimensions: [55, 60, 52, 58, 50, 60],
      strengths: ["Communication"],
      gaps: ["Front desk experience"],
      critical: ["Hospitality experience"],
      recommendations: ["Consider roles aligned with data engineering."],
    },
  ];

  let bestMatchId = "";
  for (const spec of specs) {
    const match = {
      user_id: userId,
      search_run_id: run.id,
      candidate_profile_id: candidate.id,
      job_id: insertedJobs[spec.jobIndex].id,
      overall_score: spec.overall,
      skills_score: spec.dimensions[0],
      experience_score: spec.dimensions[1],
      education_score: spec.dimensions[2],
      location_score: spec.dimensions[3],
      seniority_score: spec.dimensions[4],
      language_score: spec.dimensions[5],
      strengths: spec.strengths,
      gaps: spec.gaps,
      critical_gaps: spec.critical,
      verdict: spec.verdict,
      explanation: spec.explanation,
      recommendations: spec.recommendations,
    };
    const { data: row, error } = await client.from("job_matches").insert(match).select("id").single();
    if (error || !row) throw error ?? new Error("match insert failed");
    if (spec.overall === 92) bestMatchId = row.id;
  }

  return {
    userId,
    runId: run.id,
    bestMatchId,
    bestJobUrl: jobs[0].original_url,
  };
}

async function seedIsolationUser(client: SupabaseClient, userId: string): Promise<SeedState> {
  const { data: cv, error: cvError } = await client
    .from("cvs")
    .insert({
      user_id: userId,
      original_name: "isolation-cv.pdf",
      mime_type: "application/pdf",
      is_active: true,
      extraction_status: "extracted",
      retain_original: true,
    })
    .select("id")
    .single();
  if (cvError || !cv) throw cvError ?? new Error("isolation cv insert failed");

  const profile = {
    name: "Isolation Candidate",
    current_role: "Frontend Developer",
    seniority: "mid",
    target_roles: ["Frontend Developer"],
    skills: ["React", "TypeScript"],
    experience_years: 4,
    languages: ["English"],
    education: ["Bachelor"],
  };
  const { data: candidate, error: candidateError } = await client
    .from("candidate_profiles")
    .insert({
      user_id: userId,
      cv_id: cv.id,
      version: 1,
      profile,
      confirmed_at: new Date().toISOString(),
    })
    .select("id")
    .single();
  if (candidateError || !candidate) throw candidateError ?? new Error("isolation profile insert failed");

  const { data: searchProfile, error: searchError } = await client
    .from("search_profiles")
    .insert({
      user_id: userId,
      candidate_profile_id: candidate.id,
      region: "indonesia",
      target_roles: ["Frontend Developer"],
    })
    .select("id")
    .single();
  if (searchError || !searchProfile) throw searchError ?? new Error("isolation search profile insert failed");

  const { data: run, error: runError } = await client
    .from("job_search_runs")
    .insert({
      user_id: userId,
      search_profile_id: searchProfile.id,
      candidate_profile_id: candidate.id,
      trigger: "manual",
      status: "completed",
      discovered_count: 1,
      normalized_count: 1,
      completed_at: new Date().toISOString(),
    })
    .select("id")
    .single();
  if (runError || !run) throw runError ?? new Error("isolation run insert failed");

  const isolationJob = {
    fingerprint: "e2e-fp-iso-solo",
    title: "Isolation Private Role",
    company: "Solo Private",
    description: "A private role only this user should ever see.",
    source_name: "e2e",
    original_url: "https://example.test/jobs/isolation",
    canonical_url: "https://example.test/jobs/isolation",
    region: "indonesia",
    work_mode: "remote",
    employment_type: "full-time",
    published_at: new Date().toISOString(),
    status: "active",
  };
  const { data: job, error: jobError } = await client
    .from("jobs")
    .upsert(isolationJob, { onConflict: "fingerprint" })
    .select("id")
    .single();
  if (jobError || !job) throw jobError ?? new Error("isolation job upsert failed");

  const { data: match, error: matchError } = await client
    .from("job_matches")
    .insert({
      user_id: userId,
      search_run_id: run.id,
      candidate_profile_id: candidate.id,
      job_id: job.id,
      overall_score: 95,
      skills_score: 96,
      experience_score: 94,
      education_score: 90,
      location_score: 92,
      seniority_score: 93,
      language_score: 90,
      strengths: ["React", "TypeScript"],
      gaps: [],
      critical_gaps: [],
      verdict: "highly_recommended",
      explanation: "Private isolation match.",
      recommendations: ["Keep going."],
    })
    .select("id")
    .single();
  if (matchError || !match) throw matchError ?? new Error("isolation match insert failed");

  return {
    userId,
    runId: "",
    bestMatchId: "",
    bestJobUrl: "",
    otherUserId: userId,
    otherUserMatchId: match.id,
    otherUserJobUrl: isolationJob.original_url,
    otherUserJobTitle: isolationJob.title,
  };
}

export default async function globalSetup(): Promise<void> {
  loadEnvFile(path.resolve(__dirname, "../.env"));

  const client = createClient(
    requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requireEnv("SUPABASE_SERVICE_ROLE_KEY"),
    { auth: { persistSession: false } },
  );

  const userId = await upsertSeedUser(client, SEED_EMAIL);
  await resetUserData(client, userId);
  const state: SeedState = {
    ...(await seedMatches(client, userId)),
    otherUserId: "",
    otherUserMatchId: "",
    otherUserJobUrl: "",
    otherUserJobTitle: "",
  };

  const isolationUserId = await upsertSeedUser(client, ISOLATION_EMAIL);
  await resetUserData(client, isolationUserId);
  const isolation = await seedIsolationUser(client, isolationUserId);
  state.otherUserId = isolation.otherUserId;
  state.otherUserMatchId = isolation.otherUserMatchId;
  state.otherUserJobUrl = isolation.otherUserJobUrl;
  state.otherUserJobTitle = isolation.otherUserJobTitle;

  writeFileSync(
    path.resolve(__dirname, ".seed-state.json"),
    JSON.stringify(state, null, 2),
    "utf8",
  );
}