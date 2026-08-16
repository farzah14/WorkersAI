-- Matching and Recommendations: cached structured job requirements and
-- user-specific hybrid match results.

create table public.job_requirements (
  job_id uuid primary key references public.jobs(id) on delete cascade,
  description_hash text not null,
  requirements jsonb not null,
  extracted_at timestamptz not null default now()
);

create table public.job_matches (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  candidate_profile_id uuid not null references public.candidate_profiles(id),
  job_id uuid not null references public.jobs(id),
  overall_score integer not null check (overall_score between 0 and 100),
  skills_score integer not null check (skills_score between 0 and 100),
  experience_score integer not null check (experience_score between 0 and 100),
  education_score integer not null check (education_score between 0 and 100),
  location_score integer not null check (location_score between 0 and 100),
  seniority_score integer not null check (seniority_score between 0 and 100),
  language_score integer not null check (language_score between 0 and 100),
  strengths jsonb not null,
  gaps jsonb not null,
  critical_gaps jsonb not null,
  verdict text not null check (verdict in ('highly_recommended','recommended','potential','low_match','not_recommended')),
  explanation text not null,
  recommendations jsonb not null,
  semantic_degraded boolean not null default false,
  created_at timestamptz not null default now(),
  unique(search_run_id, job_id)
);

alter table public.job_matches enable row level security;
create policy job_matches_owner_select on public.job_matches
for select using (auth.uid() = user_id);

grant select on public.job_matches to authenticated;
grant all on public.job_requirements, public.job_matches to service_role;