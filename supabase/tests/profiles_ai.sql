begin;
select plan(8);

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
                 then has_table_privilege('anon', 'public.ai_requests', 'select')
                 else false end),
    false,
    'anon has no select on ai_requests'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.ai_requests', 'select')
                 else false end),
    false,
    'authenticated has no select on ai_requests'
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
                 then has_table_privilege('service_role', 'public.ai_requests', 'insert')
                 else false end),
    true,
    'service_role can insert ai_requests'
);

select * from finish();
rollback;