-- Per-user storage accounting for the private CV and export buckets.
--
-- Object sizes live in storage.objects.metadata->>'size'. Authenticated users
-- can already select their own objects under the bucket policies, but an
-- aggregate read still needs a security definer function so the dashboard can
-- fetch one number instead of listing every object.
--
-- The quota itself is stored per user so the UI can render "used of total".
-- A missing row means the caller falls back to the default quota.

create table public.storage_quotas (
  user_id uuid primary key references auth.users(id) on delete cascade,
  limit_bytes bigint not null default 104857600 check (limit_bytes > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.storage_quotas enable row level security;

create policy storage_quotas_owner_select on public.storage_quotas
for select to authenticated
using (auth.uid() = user_id);

grant select on public.storage_quotas to authenticated;
grant all on public.storage_quotas to service_role;

create index storage_quotas_user_idx on public.storage_quotas(user_id);

-- Returns one row describing the caller's private storage usage across both
-- application buckets. `total_bytes` is the effective quota: the user's own
-- row when present, otherwise the default.
create or replace function public.get_storage_usage()
returns table (
  used_bytes bigint,
  total_bytes bigint,
  cv_bytes bigint,
  export_bytes bigint,
  cv_count bigint,
  export_count bigint
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_user_id uuid := auth.uid();
  v_default_limit bigint := 104857600;
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;

  return query
  with owned as (
    select
      o.bucket_id,
      coalesce((o.metadata->>'size')::bigint, 0) as size_bytes
    from storage.objects o
    where (o.bucket_id = 'cvs' or o.bucket_id = 'exports')
      and (storage.foldername(o.name))[1] = v_user_id::text
  )
  select
    coalesce(sum(owned.size_bytes), 0)::bigint as used_bytes,
    coalesce(
      (select q.limit_bytes from public.storage_quotas q where q.user_id = v_user_id),
      v_default_limit
    )::bigint as total_bytes,
    coalesce(sum(owned.size_bytes) filter (where owned.bucket_id = 'cvs'), 0)::bigint as cv_bytes,
    coalesce(sum(owned.size_bytes) filter (where owned.bucket_id = 'exports'), 0)::bigint as export_bytes,
    count(*) filter (where owned.bucket_id = 'cvs')::bigint as cv_count,
    count(*) filter (where owned.bucket_id = 'exports')::bigint as export_count
  from owned;
end;
$$;

revoke all on function public.get_storage_usage() from public, anon;
grant execute on function public.get_storage_usage() to authenticated, service_role;
