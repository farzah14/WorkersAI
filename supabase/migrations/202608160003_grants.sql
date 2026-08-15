grant select, insert, update, delete on public.cvs to authenticated;
grant select, update on public.profiles to authenticated;

grant all on public.cvs, public.profiles, public.work_items to service_role;