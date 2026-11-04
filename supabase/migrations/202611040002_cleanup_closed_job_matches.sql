-- Clean up historical closed/expired jobs and their matches.

create or replace function public.cleanup_closed_job_matches()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  removed_matches integer := 0;
begin
  update public.jobs
  set status = 'expired'
  where lower(description) ~ '(^|\n|\s)(job closed|ditutup|lowongan ditutup|this job was closed|position has been filled|no longer accepting applications|job has expired)($|\n|\.|\s)';

  delete from public.job_matches
  where job_id in (select id from public.jobs where status in ('expired', 'unavailable'));

  get diagnostics removed_matches = row_count;

  delete from public.job_search_run_jobs
  where job_id in (select id from public.jobs where status in ('expired', 'unavailable'));

  return removed_matches;
end;
$$;

revoke all on function public.cleanup_closed_job_matches() from public, anon, authenticated;
grant execute on function public.cleanup_closed_job_matches() to service_role;

select public.cleanup_closed_job_matches();
