-- Purge a deleted account's queued work before the auth user is removed.
-- work_items is a global queue without a user_id foreign key; user references
-- live in the jsonb payload. Call this BEFORE auth.admin.deleteUser so the
-- cascade cannot remove the cvs/job_search_runs lookup rows first.

create or replace function public.delete_account_cleanup(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  delete from public.work_items as item
  where item.payload->>'user_id' = p_user_id::text;

  delete from public.work_items as item
  where exists (
    select 1
    from public.cvs as cv
    where cv.user_id = p_user_id
      and item.payload->>'cv_id' = cv.id::text
  );

  delete from public.work_items as item
  where exists (
    select 1
    from public.job_search_runs as run
    where run.user_id = p_user_id
      and item.payload->>'search_run_id' = run.id::text
  );
end;
$$;

revoke all on function public.delete_account_cleanup(uuid) from public, anon, authenticated;
grant execute on function public.delete_account_cleanup(uuid) to service_role;
