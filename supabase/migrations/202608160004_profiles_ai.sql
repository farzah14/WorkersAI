create table public.candidate_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  cv_id uuid not null references public.cvs(id) on delete cascade,
  version integer not null,
  profile jsonb not null,
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(cv_id, version)
);

create table public.ai_requests (
  id uuid primary key default gen_random_uuid(),
  operation text not null,
  provider text not null,
  model text not null,
  status text not null check (status in ('success','retryable_failure','permanent_failure','skipped_circuit_open')),
  latency_ms integer,
  fallback_from text,
  error_code text,
  created_at timestamptz not null default now()
);

alter table public.candidate_profiles enable row level security;
revoke all on public.ai_requests from anon, authenticated;

create policy candidate_profiles_owner_all on public.candidate_profiles
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

grant select, insert, update, delete on public.candidate_profiles to authenticated;
grant all on public.candidate_profiles, public.ai_requests to service_role;