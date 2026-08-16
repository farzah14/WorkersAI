begin;
create extension if not exists pgtap;
select plan(11);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'candidate_profiles'),
    1::bigint,
    'candidate_profiles table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'ai_requests'),
    1::bigint,
    'ai_requests table exists'
);

select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'candidate_profiles'),
    true,
    'candidate_profiles rls is enabled'
);

select is(
    (select count(*) from pg_policies
     where schemaname = 'public' and tablename = 'candidate_profiles'
       and policyname = 'candidate_profiles_owner_all' and cmd = 'ALL'),
    1::bigint,
    'candidate_profiles owner-all policy exists'
);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.ai_requests', 'select')
                   and not has_table_privilege('anon', 'public.ai_requests', 'insert')
                   and not has_table_privilege('anon', 'public.ai_requests', 'update')
                   and not has_table_privilege('anon', 'public.ai_requests', 'delete')
                   and not has_table_privilege('anon', 'public.ai_requests', 'truncate')
                   and not has_table_privilege('anon', 'public.ai_requests', 'references')
                   and not has_table_privilege('anon', 'public.ai_requests', 'trigger')
                 else false end),
    true,
    'anon has no ai_requests privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'authenticated')
                 then not has_table_privilege('authenticated', 'public.ai_requests', 'select')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'insert')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'update')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'delete')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'truncate')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'references')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'trigger')
                 else false end),
    true,
    'authenticated has no ai_requests privileges'
);

select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = 'public.candidate_profiles'::regclass
       and c.contype = 'u'
       and c.conkey @> (
           select array_agg(a.attnum)
           from pg_attribute a
           where a.attrelid = 'public.candidate_profiles'::regclass
             and a.attname in ('cv_id', 'version'))),
    1::bigint,
    'unique constraint covers (cv_id, version)'
);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.ai_requests', 'select')
                   and has_table_privilege('service_role', 'public.ai_requests', 'insert')
                   and has_table_privilege('service_role', 'public.ai_requests', 'update')
                   and has_table_privilege('service_role', 'public.ai_requests', 'delete')
                 else false end),
    true,
    'service_role can operate on ai_requests'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.candidate_profiles', 'select')
                   and has_table_privilege('authenticated', 'public.candidate_profiles', 'insert')
                   and has_table_privilege('authenticated', 'public.candidate_profiles', 'update')
                   and has_table_privilege('authenticated', 'public.candidate_profiles', 'delete')
                   and not has_table_privilege('authenticated', 'public.candidate_profiles', 'truncate')
                   and not has_table_privilege('authenticated', 'public.candidate_profiles', 'references')
                   and not has_table_privilege('authenticated', 'public.candidate_profiles', 'trigger')
                 else false end),
    true,
    'authenticated has exact candidate_profiles privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.candidate_profiles', 'select')
                   and not has_table_privilege('anon', 'public.candidate_profiles', 'insert')
                   and not has_table_privilege('anon', 'public.candidate_profiles', 'update')
                   and not has_table_privilege('anon', 'public.candidate_profiles', 'delete')
                   and not has_table_privilege('anon', 'public.candidate_profiles', 'truncate')
                   and not has_table_privilege('anon', 'public.candidate_profiles', 'references')
                   and not has_table_privilege('anon', 'public.candidate_profiles', 'trigger')
                 else false end),
    true,
    'anon has no candidate_profiles privileges'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                      and exists (select 1 from pg_roles where rolname = 'postgres')
                 then not has_function_privilege('anon', 'public.handle_new_user()', 'execute')
                   and not has_function_privilege('authenticated', 'public.handle_new_user()', 'execute')
                   and has_function_privilege('postgres', 'public.handle_new_user()', 'execute')
                 else false end),
    true,
    'handle_new_user execute is restricted to the owner'
);

select * from finish();
rollback;
