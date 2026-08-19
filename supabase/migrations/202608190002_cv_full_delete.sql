-- Remove one user's CV completely: original file is removed by the route,
-- this function purges its queued work, matches, extracted profile, and the
-- CV row itself. job_matches has no cascade on candidate_profiles, so matches
-- must be deleted before the profile rows.

create or replace function public.delete_cv(p_cv_id uuid, p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  was_active boolean;
  replacement_cv_id uuid;
begin
  select is_active
    into was_active
  from public.cvs
  where id = p_cv_id
    and user_id = p_user_id
  for update;

  if was_active is null then
    return;
  end if;

  delete from public.work_items as item
  where item.payload->>'cv_id' = p_cv_id::text;

  delete from public.work_items as item
  where exists (
    select 1
    from public.job_search_runs as run
    join public.candidate_profiles as profile on profile.id = run.candidate_profile_id
    where profile.cv_id = p_cv_id
      and item.payload->>'search_run_id' = run.id::text
  );

  delete from public.job_matches as match
  where exists (
    select 1
    from public.candidate_profiles as profile
    where profile.cv_id = p_cv_id
      and match.candidate_profile_id = profile.id
  );

  delete from public.candidate_profiles
  where cv_id = p_cv_id;

  delete from public.cvs
  where id = p_cv_id
    and user_id = p_user_id;

  if was_active then
    select id
      into replacement_cv_id
    from public.cvs
    where user_id = p_user_id
    order by created_at desc, id
    limit 1;

    if replacement_cv_id is not null then
      update public.cvs
      set is_active = true
      where id = replacement_cv_id;
    end if;
  end if;
end;
$$;

revoke all on function public.delete_cv(uuid, uuid) from public, anon, authenticated;
grant execute on function public.delete_cv(uuid, uuid) to service_role;
