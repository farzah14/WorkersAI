begin;
create extension if not exists pgtap;

select plan(13);

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

select * from finish();
rollback;
