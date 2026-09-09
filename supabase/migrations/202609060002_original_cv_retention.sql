-- Delete only the private original CV reference after storage removal while
-- preserving the CV row, extracted candidate profile, matches, and tracking.

create or replace function public.delete_original_cv(p_cv_id uuid, p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;

  update public.cvs
     set storage_path = null,
         retain_original = false
   where id = p_cv_id
     and user_id = p_user_id
     and extraction_status = 'extracted';
end;
$$;

revoke all on function public.delete_original_cv(uuid, uuid) from public, anon, authenticated;
grant execute on function public.delete_original_cv(uuid, uuid) to service_role;
