begin;
create extension if not exists pgtap;

select plan(24);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'profiles'),
    1::bigint,
    'profiles table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'cvs'),
    1::bigint,
    'cvs table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'work_items'),
    1::bigint,
    'work_items table exists'
);

select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'profiles'),
    true,
    'profiles rls is enabled'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'cvs'),
    true,
    'cvs rls is enabled'
);
select has_index('public', 'cvs', 'one_active_cv_per_user', 'partial unique index enforces one active cv');

select is(
    (select count(*) from storage.buckets where id = 'cvs' and public = false),
    1::bigint,
    'private cvs bucket exists'
);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.profiles', 'select')
                   and has_table_privilege('authenticated', 'public.profiles', 'update')
                   and not has_table_privilege('authenticated', 'public.profiles', 'insert')
                   and not has_table_privilege('authenticated', 'public.profiles', 'delete')
                   and not has_table_privilege('authenticated', 'public.profiles', 'truncate')
                   and not has_table_privilege('authenticated', 'public.profiles', 'references')
                   and not has_table_privilege('authenticated', 'public.profiles', 'trigger')
                 else false end),
    true,
    'authenticated has exact profiles privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.cvs', 'select')
                   and has_table_privilege('authenticated', 'public.cvs', 'insert')
                   and has_table_privilege('authenticated', 'public.cvs', 'update')
                   and has_table_privilege('authenticated', 'public.cvs', 'delete')
                   and not has_table_privilege('authenticated', 'public.cvs', 'truncate')
                   and not has_table_privilege('authenticated', 'public.cvs', 'references')
                   and not has_table_privilege('authenticated', 'public.cvs', 'trigger')
                 else false end),
    true,
    'authenticated has exact cvs privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.profiles', 'select')
                   and not has_table_privilege('anon', 'public.profiles', 'insert')
                   and not has_table_privilege('anon', 'public.profiles', 'update')
                   and not has_table_privilege('anon', 'public.profiles', 'delete')
                   and not has_table_privilege('anon', 'public.profiles', 'truncate')
                   and not has_table_privilege('anon', 'public.profiles', 'references')
                   and not has_table_privilege('anon', 'public.profiles', 'trigger')
                 else false end),
    true,
    'anon has no profiles privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.cvs', 'select')
                   and not has_table_privilege('anon', 'public.cvs', 'insert')
                   and not has_table_privilege('anon', 'public.cvs', 'update')
                   and not has_table_privilege('anon', 'public.cvs', 'delete')
                   and not has_table_privilege('anon', 'public.cvs', 'truncate')
                   and not has_table_privilege('anon', 'public.cvs', 'references')
                   and not has_table_privilege('anon', 'public.cvs', 'trigger')
                 else false end),
    true,
    'anon has no cvs privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.work_items', 'select')
                   and not has_table_privilege('anon', 'public.work_items', 'insert')
                   and not has_table_privilege('anon', 'public.work_items', 'update')
                   and not has_table_privilege('anon', 'public.work_items', 'delete')
                   and not has_table_privilege('anon', 'public.work_items', 'truncate')
                   and not has_table_privilege('anon', 'public.work_items', 'references')
                   and not has_table_privilege('anon', 'public.work_items', 'trigger')
                 else false end),
    true,
    'anon has no work_items privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.profiles', 'select')
                   and has_table_privilege('service_role', 'public.profiles', 'insert')
                   and has_table_privilege('service_role', 'public.profiles', 'update')
                   and has_table_privilege('service_role', 'public.profiles', 'delete')
                   and has_table_privilege('service_role', 'public.cvs', 'select')
                   and has_table_privilege('service_role', 'public.cvs', 'insert')
                   and has_table_privilege('service_role', 'public.cvs', 'update')
                   and has_table_privilege('service_role', 'public.cvs', 'delete')
                   and has_table_privilege('service_role', 'public.work_items', 'select')
                   and has_table_privilege('service_role', 'public.work_items', 'insert')
                   and has_table_privilege('service_role', 'public.work_items', 'update')
                   and has_table_privilege('service_role', 'public.work_items', 'delete')
                 else false end),
    true,
    'service_role can operate on core user and worker tables'
);

select has_function(
    'public',
    'delete_original_cv',
    array['uuid', 'uuid'],
    'original CV deletion function exists'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_function_privilege('service_role', 'public.delete_original_cv(uuid, uuid)', 'execute')
                   and not has_function_privilege('authenticated', 'public.delete_original_cv(uuid, uuid)', 'execute')
                   and not has_function_privilege('anon', 'public.delete_original_cv(uuid, uuid)', 'execute')
                   and not exists (
                       select 1
                       from pg_proc as procedure
                       cross join lateral aclexplode(coalesce(procedure.proacl, acldefault('f', procedure.proowner))) as privilege
                       where procedure.oid = 'public.delete_original_cv(uuid, uuid)'::regprocedure
                         and privilege.grantee = 0
                         and privilege.privilege_type = 'EXECUTE'
                   )
                 else false end),
    true,
    'only service_role can execute original CV deletion'
);

insert into auth.users (id, email)
values
    ('00000000-0000-0000-0000-000000000001', 'cv-owner@example.com'),
    ('00000000-0000-0000-0000-000000000002', 'other-owner@example.com');

insert into public.cvs (
    id,
    user_id,
    original_name,
    mime_type,
    storage_path,
    retain_original,
    extraction_status
)
values (
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'resume.pdf',
    'application/pdf',
    '00000000-0000-0000-0000-000000000001/10000000-0000-0000-0000-000000000001/resume.pdf',
    true,
    'extracted'
);

insert into public.cvs (
    id,
    user_id,
    original_name,
    mime_type,
    storage_path,
    retain_original,
    extraction_status
)
values (
    '10000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    'queued-resume.pdf',
    'application/pdf',
    '00000000-0000-0000-0000-000000000001/10000000-0000-0000-0000-000000000002/queued-resume.pdf',
    true,
    'queued'
);

insert into public.candidate_profiles (id, user_id, cv_id, version, profile)
values (
    '20000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    1,
    '{}'::jsonb
);

select set_config('request.jwt.claims', '', true);
select throws_ok(
    $$select public.delete_original_cv(
        '10000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000001'
    )$$,
    '42501',
    'service_role_required',
    'original CV deletion rejects callers without service claims'
);

select set_config('request.jwt.claims', '{"role":"authenticated"}', true);
select throws_ok(
    $$select public.delete_original_cv(
        '10000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000001'
    )$$,
    '42501',
    'service_role_required',
    'original CV deletion rejects non-service callers'
);

select set_config('request.jwt.claims', '{"role":"service_role"}', true);
select public.delete_original_cv(
    '10000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001'
);
select is(
    (select storage_path from public.cvs where id = '10000000-0000-0000-0000-000000000002'),
    '00000000-0000-0000-0000-000000000001/10000000-0000-0000-0000-000000000002/queued-resume.pdf',
    'original deletion preserves storage path until extraction completes'
);
select is(
    (select retain_original from public.cvs where id = '10000000-0000-0000-0000-000000000002'),
    true,
    'original deletion preserves retention until extraction completes'
);

select public.delete_original_cv(
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000002'
);
select is(
    (select storage_path from public.cvs where id = '10000000-0000-0000-0000-000000000001'),
    '00000000-0000-0000-0000-000000000001/10000000-0000-0000-0000-000000000001/resume.pdf',
    'wrong-owner deletion leaves the original reference unchanged'
);

select public.delete_original_cv(
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001'
);
select is(
    (select count(*) from public.cvs where id = '10000000-0000-0000-0000-000000000001'),
    1::bigint,
    'original deletion preserves the CV row'
);
select is(
    (select count(*) from public.candidate_profiles where id = '20000000-0000-0000-0000-000000000001'),
    1::bigint,
    'original deletion preserves the candidate profile'
);
select is(
    (select storage_path from public.cvs where id = '10000000-0000-0000-0000-000000000001'),
    null::text,
    'original deletion clears the storage path'
);
select is(
    (select retain_original from public.cvs where id = '10000000-0000-0000-0000-000000000001'),
    false,
    'original deletion disables original retention'
);

select * from finish();
rollback;
