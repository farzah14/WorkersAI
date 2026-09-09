create or replace function public.save_candidate_profile(
  p_cv_id uuid,
  p_profile jsonb
) returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_user_id uuid := auth.uid();
  v_version integer;
begin
  if v_user_id is null then
    raise exception 'unauthorized' using errcode = '42501';
  end if;

  perform 1 from public.cvs where id = p_cv_id and user_id = v_user_id for update;
  if not found then
    raise exception 'cv_not_found' using errcode = 'P0001';
  end if;

  select coalesce(max(version), 0) + 1 into v_version
  from public.candidate_profiles where cv_id = p_cv_id;

  insert into public.candidate_profiles(user_id, cv_id, version, profile, confirmed_at)
  values (v_user_id, p_cv_id, v_version, p_profile, now());

  update public.cvs set is_active = false where user_id = v_user_id and id <> p_cv_id and is_active;
  update public.cvs set is_active = true where id = p_cv_id and user_id = v_user_id;

  update public.search_profiles set candidate_profile_id = (
    select id from public.candidate_profiles where cv_id = p_cv_id and version = v_version
  ) where user_id = v_user_id and is_current;

  return v_version;
end;
$$;

revoke all on function public.save_candidate_profile(uuid, jsonb) from public, anon, authenticated;
grant execute on function public.save_candidate_profile(uuid, jsonb) to authenticated;
