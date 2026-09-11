-- Reclassify historical zero-result runs where at least one source succeeded
-- and another source failed. These are partial searches, not total failures.

create or replace function public.reclassify_mixed_source_zero_result_runs()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  updated_runs integer := 0;
begin
  update public.job_search_runs as run
  set status = 'partial'
  where run.status = 'failed'
    and run.normalized_count = 0
    and not exists (
      select 1
      from public.job_matches as match
      where match.search_run_id = run.id
    )
    and exists (
      select 1
      from public.job_sources as source
      where source.search_run_id = run.id
        and source.status = 'success'
    )
    and exists (
      select 1
      from public.job_sources as source
      where source.search_run_id = run.id
        and source.status = 'failed'
    );

  get diagnostics updated_runs = row_count;
  return updated_runs;
end;
$$;

revoke all on function public.reclassify_mixed_source_zero_result_runs()
  from public, anon, authenticated;
grant execute on function public.reclassify_mixed_source_zero_result_runs()
  to service_role;

select public.reclassify_mixed_source_zero_result_runs();
