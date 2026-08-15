create extension if not exists pgcrypto;

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  locale text not null default 'id' check (locale in ('id','en')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.cvs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  original_name text not null,
  mime_type text not null check (mime_type in ('application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
  storage_path text,
  retain_original boolean not null default true,
  is_active boolean not null default false,
  extraction_status text not null default 'queued' check (extraction_status in ('queued','processing','extracted','failed')),
  extracted_text text,
  extraction_error text,
  created_at timestamptz not null default now()
);

create unique index one_active_cv_per_user on public.cvs(user_id) where is_active;

create table public.work_items (
  id uuid primary key default gen_random_uuid(),
  kind text not null,
  dedupe_key text not null unique,
  payload jsonb not null,
  status text not null default 'queued' check (status in ('queued','processing','completed','failed')),
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  available_at timestamptz not null default now(),
  locked_at timestamptz,
  locked_by text,
  last_error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.profiles enable row level security;
alter table public.cvs enable row level security;
revoke all on public.work_items from anon, authenticated;

create policy profiles_owner_all on public.profiles
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy cvs_owner_all on public.cvs
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

insert into storage.buckets (id, name, public)
values ('cvs','cvs',false)
on conflict (id) do update set public = false;

create policy cv_storage_owner_select on storage.objects
for select to authenticated
using (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);

create policy cv_storage_owner_insert on storage.objects
for insert to authenticated
with check (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);

create policy cv_storage_owner_delete on storage.objects
for delete to authenticated
using (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);