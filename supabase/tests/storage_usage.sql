begin;
create extension if not exists pgtap;

select plan(14);

-- Schema and privilege surface -------------------------------------------------

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'storage_quotas'),
    1::bigint,
    'storage_quotas table exists'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'storage_quotas'),
    true,
    'storage_quotas rls is enabled'
);
select is(
    (select count(*) from pg_policies
     where schemaname = 'public' and tablename = 'storage_quotas'
       and policyname = 'storage_quotas_owner_select'),
    1::bigint,
    'storage_quotas exposes an owner select policy'
);
select is(
    (select count(*) from pg_proc p
     where p.proname = 'get_storage_usage' and p.prosecdef),
    1::bigint,
    'get_storage_usage is security definer'
);
select is(
    (select count(*) from pg_proc p
     where p.proname = 'get_storage_usage'
       and has_function_privilege('authenticated', p.oid, 'EXECUTE')),
    1::bigint,
    'authenticated role can execute storage usage function'
);
select is(
    (select count(*) from pg_proc p
     where p.proname = 'get_storage_usage'
       and has_function_privilege('anon', p.oid, 'EXECUTE')),
    0::bigint,
    'anon cannot execute storage usage function'
);

-- Fixtures ---------------------------------------------------------------------

insert into auth.users (id, email)
values
    ('00000000-0000-0000-0000-0000000000a1', 'storage-usage@example.test'),
    ('00000000-0000-0000-0000-0000000000a2', 'storage-other@example.test');

insert into storage.objects (bucket_id, name, metadata)
values
    ('cvs', '00000000-0000-0000-0000-0000000000a1/cv-1/resume.pdf', '{"size": 1048576}'),
    ('cvs', '00000000-0000-0000-0000-0000000000a1/cv-2/resume.docx', '{"size": 2097152}'),
    ('exports', '00000000-0000-0000-0000-0000000000a1/export-1/report.xlsx', '{"size": 4194304}'),
    ('cvs', '00000000-0000-0000-0000-0000000000a2/other/resume.pdf', '{"size": 8388608}');

-- Aggregation ------------------------------------------------------------------

select set_config(
    'request.jwt.claims',
    '{"sub":"00000000-0000-0000-0000-0000000000a1","role":"authenticated"}',
    true
);
set local role authenticated;

select is(
    (select used_bytes from public.get_storage_usage()),
    7340032::bigint,
    'used_bytes sums only the caller objects across both buckets'
);
select is(
    (select cv_bytes from public.get_storage_usage()),
    3145728::bigint,
    'cv_bytes covers only the cvs bucket'
);
select is(
    (select export_bytes from public.get_storage_usage()),
    4194304::bigint,
    'export_bytes covers only the exports bucket'
);
select is(
    (select cv_count from public.get_storage_usage()),
    2::bigint,
    'cv_count counts the caller CV objects'
);
select is(
    (select export_count from public.get_storage_usage()),
    1::bigint,
    'export_count counts the caller export objects'
);

-- Quota fallback and override --------------------------------------------------

select is(
    (select total_bytes from public.get_storage_usage()),
    104857600::bigint,
    'missing quota row falls back to the default limit'
);

reset role;
select set_config('request.jwt.claims', '{"role":"service_role"}', true);
set local role service_role;

insert into public.storage_quotas (user_id, limit_bytes)
values ('00000000-0000-0000-0000-0000000000a1', 52428800);

select set_config(
    'request.jwt.claims',
    '{"sub":"00000000-0000-0000-0000-0000000000a1","role":"authenticated"}',
    true
);
set local role authenticated;

select is(
    (select total_bytes from public.get_storage_usage()),
    52428800::bigint,
    'per-user quota row overrides the default limit'
);

-- Isolation --------------------------------------------------------------------

select set_config(
    'request.jwt.claims',
    '{"sub":"00000000-0000-0000-0000-0000000000a2","role":"authenticated"}',
    true
);

select is(
    (select used_bytes from public.get_storage_usage()),
    8388608::bigint,
    'another user sees only their own usage'
);

select set_config('request.jwt.claims', '{"role":"authenticated"}', true);
select throws_ok(
    $$select * from public.get_storage_usage()$$,
    '42501', 'authentication_required',
    'authenticated role without a user identity cannot read usage'
);

select * from finish();
rollback;
