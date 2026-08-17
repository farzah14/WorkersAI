create table public.api_usage_windows (
  user_id uuid not null references auth.users(id) on delete cascade,
  action text not null,
  window_start timestamptz not null,
  count integer not null default 0,
  primary key (user_id, action, window_start)
);

alter table public.api_usage_windows enable row level security;

grant all on public.api_usage_windows to service_role;

alter table public.job_search_runs
add column idempotency_key text;

create unique index job_search_runs_idempotency_key_unique
on public.job_search_runs(idempotency_key)
where idempotency_key is not null;

create index work_items_ready_idx
on public.work_items(status, available_at, created_at)
where status = 'queued';

create or replace function public.increment_api_usage(
  p_user_id uuid,
  p_action text
) returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_window timestamptz := date_trunc('day', now());
  v_count integer;
begin
  insert into public.api_usage_windows (user_id, action, window_start, count)
  values (p_user_id, p_action, v_window, 1)
  on conflict (user_id, action, window_start)
  do update set count = api_usage_windows.count + 1
  returning count into v_count;
  return v_count;
end;
$$;

revoke all on function public.increment_api_usage(uuid, text) from public;
grant execute on function public.increment_api_usage(uuid, text) to authenticated, service_role;