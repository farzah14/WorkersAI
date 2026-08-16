alter table public.cvs
  add constraint cvs_user_id_id_key unique (user_id, id);

-- Fail fast on legacy rows that would break the ownership foreign key before
-- installing candidate_profiles_user_cv_fk. This preflight is safe on empty
-- databases (count of zero raises nothing).
do $$
declare
  orphan_count bigint;
begin
  select count(*)
    into orphan_count
  from public.candidate_profiles as candidate_profiles
  where not exists (
    select 1
    from public.cvs
    where cvs.id = candidate_profiles.cv_id
      and cvs.user_id = candidate_profiles.user_id
  );

  if orphan_count > 0 then
    raise exception using
      errcode = 'check_violation',
      message = format(
        'Cannot add candidate_profiles_user_cv_fk: found %s candidate profile row(s) whose (user_id, cv_id) has no matching cvs(user_id, id) row.',
        orphan_count
      ),
      hint = 'Remediate the orphaned candidate profile rows and rerun the migration. No user data was changed by this preflight.';
  end if;
end;
$$;

alter table public.candidate_profiles
  add constraint candidate_profiles_user_id_id_key unique (user_id, id);

alter table public.candidate_profiles
  add constraint candidate_profiles_user_cv_fk
  foreign key (user_id, cv_id)
  references public.cvs(user_id, id) on delete cascade;

create function public.text_array_has_no_blank_elements(items text[])
returns boolean
language sql
immutable
parallel safe
as $$
  select items is not null
    and cardinality(items) > 0
    and not exists (
      select 1
      from unnest(items) as item(value)
      where value is null or btrim(value) = ''
    );
$$;

revoke all on function public.handle_new_user()
  from PUBLIC, anon, authenticated;
grant execute on function public.handle_new_user() to postgres;

revoke all on function public.text_array_has_no_blank_elements(text[])
  from PUBLIC, anon, authenticated;
grant execute on function public.text_array_has_no_blank_elements(text[])
  to service_role;

alter default privileges for role postgres
  revoke all on functions from PUBLIC, anon, authenticated;
alter default privileges for role postgres
  revoke all on sequences from PUBLIC, anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on tables from PUBLIC, anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on functions from PUBLIC, anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from PUBLIC, anon, authenticated;

create table public.search_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  candidate_profile_id uuid not null references public.candidate_profiles(id) on delete cascade,
  region text not null check (region in ('indonesia','global')),
  target_roles text[] not null,
  locations text[] not null default '{}',
  work_modes text[] not null default '{}',
  employment_types text[] not null default '{full-time}',
  min_salary numeric,
  salary_currency text,
  excluded_keywords text[] not null default '{}',
  daily_enabled boolean not null default false,
  is_current boolean not null default true,
  created_at timestamptz not null default now(),
  constraint search_profiles_user_id_id_key unique (user_id, id),
  constraint search_profiles_id_candidate_profile_id_key unique (id, candidate_profile_id),
  constraint search_profiles_user_candidate_profile_fk
    foreign key (user_id, candidate_profile_id)
    references public.candidate_profiles(user_id, id) on delete cascade,
  constraint search_profiles_target_roles_non_empty_check
    check (public.text_array_has_no_blank_elements(target_roles)),
  constraint search_profiles_work_modes_check
    check (work_modes <@ ARRAY['remote','hybrid','on-site']::text[]),
  constraint search_profiles_min_salary_check
    check (min_salary is null or min_salary >= 0)
);

create table public.job_search_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  search_profile_id uuid not null references public.search_profiles(id) on delete cascade,
  candidate_profile_id uuid not null references public.candidate_profiles(id) on delete cascade,
  trigger text not null check (trigger in ('manual','daily')),
  status text not null default 'queued' check (status in ('queued','processing','completed','partial','failed')),
  discovered_count integer not null default 0,
  normalized_count integer not null default 0,
  duplicate_count integer not null default 0,
  failed_count integer not null default 0,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  constraint job_search_runs_user_search_profile_fk
    foreign key (user_id, search_profile_id)
    references public.search_profiles(user_id, id) on delete cascade,
  constraint job_search_runs_user_candidate_profile_fk
    foreign key (user_id, candidate_profile_id)
    references public.candidate_profiles(user_id, id) on delete cascade,
  constraint job_search_runs_search_profile_candidate_profile_fk
    foreign key (search_profile_id, candidate_profile_id)
    references public.search_profiles(id, candidate_profile_id) on delete cascade,
  constraint job_search_runs_counts_non_negative_check
    check (
      discovered_count >= 0
      and normalized_count >= 0
      and duplicate_count >= 0
      and failed_count >= 0
    )
);

create table public.job_sources (
  id uuid primary key default gen_random_uuid(),
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  source_type text not null,
  source_key text not null,
  status text not null default 'queued' check (status in ('queued','success','failed','skipped')),
  result_count integer not null default 0,
  error_code text,
  created_at timestamptz not null default now(),
  constraint job_sources_run_source_key_key unique (search_run_id, source_type, source_key),
  constraint job_sources_required_text_non_empty_check
    check (btrim(source_type) <> '' and btrim(source_key) <> ''),
  constraint job_sources_result_count_non_negative_check
    check (result_count >= 0)
);

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null,
  title text not null,
  company text not null,
  location text,
  country text,
  -- Unknown keeps source records filterable when a connector cannot classify region.
  region text not null default 'unknown',
  work_mode text,
  employment_type text,
  salary_min numeric,
  salary_max numeric,
  salary_currency text,
  description text not null,
  source_name text not null,
  original_url text not null,
  canonical_url text not null,
  published_at timestamptz,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_checked_at timestamptz not null default now(),
  status text not null default 'active' check (status in ('active','expired','unavailable','unknown')),
  constraint jobs_fingerprint_key unique (fingerprint),
  constraint jobs_fingerprint_non_empty_check
    check (btrim(fingerprint) <> ''),
  constraint jobs_required_text_non_empty_check
    check (
      btrim(title) <> ''
      and btrim(company) <> ''
      and btrim(description) <> ''
      and btrim(source_name) <> ''
      and btrim(original_url) <> ''
      and btrim(canonical_url) <> ''
    ),
  constraint jobs_salary_bounds_check
    check (
      (salary_min is null or salary_min >= 0)
      and (salary_max is null or salary_max >= 0)
      and (salary_min is null or salary_max is null or salary_min <= salary_max)
    ),
  constraint jobs_work_mode_check
    check (work_mode is null or work_mode in ('remote','hybrid','on-site')),
  constraint jobs_region_check
    check (region in ('indonesia','global','unknown'))
);

create table public.job_search_run_jobs (
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  job_id uuid not null references public.jobs(id) on delete restrict,
  primary key(search_run_id, job_id)
);

create table public.job_provenance (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null references public.jobs(id) on delete restrict,
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  source_type text not null,
  source_key text not null,
  original_url text not null,
  canonical_url text not null,
  created_at timestamptz not null default now(),
  constraint job_provenance_run_job_source_key unique
    (search_run_id, job_id, source_type, source_key),
  constraint job_provenance_run_job_fk
    foreign key (search_run_id, job_id)
    references public.job_search_run_jobs(search_run_id, job_id) on delete cascade,
  constraint job_provenance_source_fk
    foreign key (search_run_id, source_type, source_key)
    references public.job_sources(search_run_id, source_type, source_key) on delete cascade,
  constraint job_provenance_required_text_non_empty_check
    check (
      btrim(source_type) <> ''
      and btrim(source_key) <> ''
      and btrim(original_url) <> ''
      and btrim(canonical_url) <> ''
    )
);

create index search_profiles_user_id_idx
  on public.search_profiles(user_id);

create unique index search_profiles_current_user_idx
  on public.search_profiles(user_id)
  where is_current;

create index search_profiles_candidate_profile_id_idx
  on public.search_profiles(candidate_profile_id);

create index candidate_profiles_user_cv_idx
  on public.candidate_profiles(user_id, cv_id);

create index search_profiles_user_candidate_profile_idx
  on public.search_profiles(user_id, candidate_profile_id);

create index job_search_runs_user_created_at_idx
  on public.job_search_runs(user_id, created_at desc);

create index job_search_runs_user_search_profile_idx
  on public.job_search_runs(user_id, search_profile_id);

create index job_search_runs_user_candidate_profile_idx
  on public.job_search_runs(user_id, candidate_profile_id);

create index job_search_runs_search_profile_candidate_profile_idx
  on public.job_search_runs(search_profile_id, candidate_profile_id);

create index job_search_runs_search_profile_id_idx
  on public.job_search_runs(search_profile_id);

create index job_search_runs_candidate_profile_id_idx
  on public.job_search_runs(candidate_profile_id);

create index job_sources_search_run_id_idx
  on public.job_sources(search_run_id);

create index jobs_canonical_url_idx
  on public.jobs(canonical_url);

create index jobs_status_published_at_idx
  on public.jobs(status, published_at desc);

create index job_search_run_jobs_job_id_idx
  on public.job_search_run_jobs(job_id);

create index job_provenance_job_id_idx
  on public.job_provenance(job_id);

create index job_provenance_search_run_source_idx
  on public.job_provenance(search_run_id, source_type, source_key);

alter table public.search_profiles enable row level security;
alter table public.job_search_runs enable row level security;
alter table public.job_sources enable row level security;
alter table public.job_search_run_jobs enable row level security;
alter table public.job_provenance enable row level security;

create policy search_profiles_owner_all on public.search_profiles
for all to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy job_search_runs_owner_all on public.job_search_runs
for all to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy job_sources_owner_all on public.job_sources
for all to authenticated
using (
  exists (
    select 1
    from public.job_search_runs as runs
    where runs.id = job_sources.search_run_id
      and runs.user_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1
    from public.job_search_runs as runs
    where runs.id = job_sources.search_run_id
      and runs.user_id = (select auth.uid())
  )
);

create policy job_search_run_jobs_owner_all on public.job_search_run_jobs
for all to authenticated
using (
  exists (
    select 1
    from public.job_search_runs as runs
    where runs.id = job_search_run_jobs.search_run_id
      and runs.user_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1
    from public.job_search_runs as runs
    where runs.id = job_search_run_jobs.search_run_id
      and runs.user_id = (select auth.uid())
  )
);

create policy job_provenance_owner_all on public.job_provenance
for all to authenticated
using (
  exists (
    select 1
    from public.job_search_runs as runs
    where runs.id = job_provenance.search_run_id
      and runs.user_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1
    from public.job_search_runs as runs
    where runs.id = job_provenance.search_run_id
      and runs.user_id = (select auth.uid())
  )
);

revoke all on public.search_profiles, public.job_search_runs,
  public.job_sources, public.job_search_run_jobs, public.jobs,
  public.job_provenance
  from PUBLIC, anon, authenticated;

revoke all on public.work_items, public.ai_requests
  from PUBLIC, anon, authenticated;

grant select
  on public.search_profiles, public.job_search_runs
  to authenticated;

grant select
  on public.job_sources, public.job_search_run_jobs, public.jobs, public.job_provenance
  to authenticated;

grant all on public.search_profiles, public.job_search_runs,
  public.job_sources, public.jobs, public.job_search_run_jobs,
  public.job_provenance
  to service_role;

revoke all on public.profiles, public.cvs, public.candidate_profiles,
  public.work_items, public.ai_requests
  from PUBLIC, anon, authenticated;

grant select, update on public.profiles to authenticated;
grant select, insert, update, delete on public.cvs, public.candidate_profiles
  to authenticated;

grant all on public.profiles, public.cvs, public.candidate_profiles,
  public.work_items, public.ai_requests
  to service_role;

create or replace function public.create_manual_search_run(
  p_user_id uuid,
  p_candidate_profile_id uuid,
  p_region text,
  p_target_roles text[],
  p_locations text[],
  p_work_modes text[],
  p_employment_types text[],
  p_min_salary numeric,
  p_salary_currency text,
  p_excluded_keywords text[],
  p_daily_enabled boolean
)
returns table(search_run_id uuid)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_search_profile_id uuid;
  v_search_run_id uuid;
begin
  if p_region is null or p_region not in ('indonesia', 'global')
     or not public.text_array_has_no_blank_elements(p_target_roles)
     or p_work_modes is null
     or not (p_work_modes <@ ARRAY['remote', 'hybrid', 'on-site']::text[])
     or p_employment_types is null
     or not (
       p_employment_types <@ ARRAY[
         'full-time', 'part-time', 'contract', 'temporary',
         'internship', 'apprenticeship', 'volunteer', 'freelance'
       ]::text[]
     )
     or (p_min_salary is not null and p_min_salary < 0) then
    raise exception using
      errcode = '22023',
      message = 'invalid_search_profile';
  end if;

  if not exists (
    select 1
    from public.candidate_profiles as candidate_profiles
    join public.cvs as cvs
      on cvs.id = candidate_profiles.cv_id
     and cvs.user_id = candidate_profiles.user_id
    where candidate_profiles.id = p_candidate_profile_id
      and candidate_profiles.user_id = p_user_id
      and candidate_profiles.confirmed_at is not null
      and cvs.is_active
  ) then
    raise exception using
      errcode = 'P0001',
      message = 'confirmed_active_profile_required';
  end if;

  update public.search_profiles
  set is_current = false
  where user_id = p_user_id
    and is_current;

  insert into public.search_profiles (
    user_id,
    candidate_profile_id,
    region,
    target_roles,
    locations,
    work_modes,
    employment_types,
    min_salary,
    salary_currency,
    excluded_keywords,
    daily_enabled,
    is_current
  )
  values (
    p_user_id,
    p_candidate_profile_id,
    p_region,
    p_target_roles,
    coalesce(p_locations, '{}'::text[]),
    coalesce(p_work_modes, '{}'::text[]),
    coalesce(p_employment_types, '{full-time}'::text[]),
    p_min_salary,
    p_salary_currency,
    coalesce(p_excluded_keywords, '{}'::text[]),
    coalesce(p_daily_enabled, false),
    true
  )
  returning id into v_search_profile_id;

  insert into public.job_search_runs (
    user_id,
    search_profile_id,
    candidate_profile_id,
    trigger
  )
  values (
    p_user_id,
    v_search_profile_id,
    p_candidate_profile_id,
    'manual'
  )
  returning id into v_search_run_id;

  insert into public.work_items (kind, dedupe_key, payload)
  values (
    'discover_jobs',
    'discover_jobs:' || v_search_run_id::text,
    jsonb_build_object(
      'search_run_id', v_search_run_id,
      'search_profile_id', v_search_profile_id,
      'candidate_profile_id', p_candidate_profile_id,
      'user_id', p_user_id
    )
  )
  on conflict (dedupe_key) do nothing;

  return query select v_search_run_id;
end;
$$;

revoke all on function public.create_manual_search_run(
  uuid, uuid, text, text[], text[], text[], text[], numeric, text, text[], boolean
) from public, anon, authenticated;
grant execute on function public.create_manual_search_run(
  uuid, uuid, text, text[], text[], text[], text[], numeric, text, text[], boolean
) to service_role;
