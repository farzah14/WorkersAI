-- Safely remove one user's terminal search run and its queued work.

create or replace function public.delete_search_run(p_run_id uuid, p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  run_status text;
begin
  select status
    into run_status
  from public.job_search_runs
  where id = p_run_id
    and user_id = p_user_id
  for update;

  if run_status is null then
    raise exception 'search_run_not_found' using errcode = 'P0002';
  end if;

  if run_status not in ('completed', 'partial', 'failed') then
    raise exception 'search_run_active' using errcode = 'P0001';
  end if;

  delete from public.work_items
  where payload->>'search_run_id' = p_run_id::text;

  delete from public.work_items as item
  where item.kind = 'extract_job_requirements'
    and exists (
      select 1
      from public.job_search_run_jobs as run_job
      where run_job.search_run_id = p_run_id
        and item.payload->>'job_id' = run_job.job_id::text
        and not exists (
          select 1
          from public.job_search_run_jobs as other_run_job
          where other_run_job.job_id = run_job.job_id
            and other_run_job.search_run_id <> p_run_id
        )
    );

  delete from public.job_search_runs
  where id = p_run_id
    and user_id = p_user_id;
end;
$$;

revoke all on function public.delete_search_run(uuid, uuid) from public, anon, authenticated;
grant execute on function public.delete_search_run(uuid, uuid) to service_role;
