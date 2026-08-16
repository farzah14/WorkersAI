create table public.user_jobs (
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references public.jobs(id) on delete cascade,
  status text not null check (status in ('new','saved','applied','ignored')),
  applied_at timestamptz,
  updated_at timestamptz not null default now(),
  primary key(user_id, job_id)
);

create table public.exports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  format text not null check (format in ('xlsx','pdf')),
  filter_json jsonb not null,
  status text not null default 'queued' check (status in ('queued','processing','completed','failed')),
  storage_path text,
  error_code text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.user_jobs enable row level security;
alter table public.exports enable row level security;

create policy user_jobs_owner_all on public.user_jobs
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy exports_owner_all on public.exports
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

insert into storage.buckets (id, name, public)
values ('exports','exports',false)
on conflict (id) do update set public = false;

create policy export_storage_owner_select on storage.objects
for select to authenticated
using (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);

create policy export_storage_owner_insert on storage.objects
for insert to authenticated
with check (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);

create policy export_storage_owner_delete on storage.objects
for delete to authenticated
using (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);

grant select, insert, update, delete on public.user_jobs to authenticated;
grant select, insert on public.exports to authenticated;

grant all on public.user_jobs, public.exports to service_role;