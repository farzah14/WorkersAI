create or replace function public.increment_api_usage(
  p_user_id uuid,
  p_action text
) returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_user_id uuid := auth.uid();
  v_role text := auth.role();
  v_window timestamptz := date_trunc('day', now());
  v_count integer;
begin
  if v_role is distinct from 'service_role'
    and (v_user_id is null or v_user_id is distinct from p_user_id) then
    raise exception using errcode = '42501', message = 'quota_user_mismatch';
  end if;

  insert into public.api_usage_windows (user_id, action, window_start, count)
  values (p_user_id, p_action, v_window, 1)
  on conflict (user_id, action, window_start)
  do update set count = api_usage_windows.count + 1
  returning count into v_count;
  return v_count;
end;
$$;

revoke all on function public.increment_api_usage(uuid, text) from public, anon, authenticated, service_role;
grant execute on function public.increment_api_usage(uuid, text) to authenticated, service_role;
