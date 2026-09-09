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
  v_candidate_profile_id uuid;
  v_search_profile_id uuid;
begin
  if v_user_id is null then
    raise exception 'unauthorized' using errcode = '42501';
  end if;

  perform 1 from public.cvs where id = p_cv_id and user_id = v_user_id for update;
  if not found then
    raise exception 'cv_not_found' using errcode = 'P0001';
  end if;

  select id
    into v_search_profile_id
  from public.search_profiles
  where user_id = v_user_id
    and is_current
  for update;

  select coalesce(max(version), 0) + 1 into v_version
  from public.candidate_profiles where cv_id = p_cv_id;

  insert into public.candidate_profiles(user_id, cv_id, version, profile, confirmed_at)
  values (v_user_id, p_cv_id, v_version, p_profile, now())
  returning id into v_candidate_profile_id;

  update public.cvs set is_active = false where user_id = v_user_id and id <> p_cv_id and is_active;
  update public.cvs set is_active = true where id = p_cv_id and user_id = v_user_id;

  if v_search_profile_id is not null then
    update public.search_profiles
    set is_current = false
    where id = v_search_profile_id;

    insert into public.search_profiles (
      user_id,
      candidate_profile_id,
      region,
      target_roles,
      locations,
      work_modes,
      employment_types,
      min_salary,
      salary_currency,
      excluded_keywords,
      daily_enabled,
      is_current
    )
    select
      user_id,
      v_candidate_profile_id,
      region,
      target_roles,
      locations,
      work_modes,
      employment_types,
      min_salary,
      salary_currency,
      excluded_keywords,
      daily_enabled,
      true
    from public.search_profiles
    where id = v_search_profile_id;
  end if;

  return v_version;
end;
$$;

revoke all on function public.save_candidate_profile(uuid, jsonb) from public, anon, authenticated;
grant execute on function public.save_candidate_profile(uuid, jsonb) to authenticated;
