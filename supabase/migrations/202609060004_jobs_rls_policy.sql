-- Ensure authenticated users can select from public.jobs for matching and dashboard views.
alter table public.jobs enable row level security;

drop policy if exists jobs_authenticated_select on public.jobs;
create policy jobs_authenticated_select on public.jobs
  for select to authenticated using (true);

grant select on public.jobs to authenticated;
