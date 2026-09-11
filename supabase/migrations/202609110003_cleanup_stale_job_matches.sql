-- Remove stale, future-dated, and undated search results from every region.
-- Shared jobs and user_jobs tracking state remain intact.

create or replace function public.cleanup_stale_job_matches()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  removed_matches integer := 0;
begin
  delete from public.job_matches as match
  using public.jobs as job
  where match.job_id = job.id
    and (
      job.published_at is null
      or job.published_at > now()
      or (job.published_at at time zone 'utc')::date
        < (now() at time zone 'utc')::date - 30
    );

  get diagnostics removed_matches = row_count;

  delete from public.job_search_run_jobs as run_job
  using public.jobs as job
  where run_job.job_id = job.id
    and (
      job.published_at is null
      or job.published_at > now()
      or (job.published_at at time zone 'utc')::date
        < (now() at time zone 'utc')::date - 30
    );

  return removed_matches;
end;
$$;

revoke all on function public.cleanup_stale_job_matches() from public, anon, authenticated;
grant execute on function public.cleanup_stale_job_matches() to service_role;

select public.cleanup_stale_job_matches();
