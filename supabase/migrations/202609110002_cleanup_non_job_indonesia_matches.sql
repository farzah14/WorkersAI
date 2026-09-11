-- Remove content and search pages that were incorrectly treated as Indonesia
-- job postings. Preserve shared jobs and user_jobs tracking state.

create or replace function public.cleanup_non_job_indonesia_matches()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  removed_matches integer := 0;
begin
  delete from public.job_matches as match
  using public.job_search_runs as run,
        public.search_profiles as profile,
        public.jobs as job
  where match.search_run_id = run.id
    and run.search_profile_id = profile.id
    and match.job_id = job.id
    and profile.region = 'indonesia'
    and lower(coalesce(job.canonical_url, job.original_url, '')) ~
      '/(articles|blog|career-advice|career-guide|job-search|jobs/search|resources|salaries|salary)(/|$)';

  get diagnostics removed_matches = row_count;

  delete from public.job_search_run_jobs as run_job
  using public.job_search_runs as run,
        public.search_profiles as profile,
        public.jobs as job
  where run_job.search_run_id = run.id
    and run.search_profile_id = profile.id
    and run_job.job_id = job.id
    and profile.region = 'indonesia'
    and lower(coalesce(job.canonical_url, job.original_url, '')) ~
      '/(articles|blog|career-advice|career-guide|job-search|jobs/search|resources|salaries|salary)(/|$)';

  return removed_matches;
end;
$$;

revoke all on function public.cleanup_non_job_indonesia_matches() from public, anon, authenticated;
grant execute on function public.cleanup_non_job_indonesia_matches() to service_role;

select public.cleanup_non_job_indonesia_matches();
