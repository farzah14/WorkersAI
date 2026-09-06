begin;
create extension if not exists pgtap;
select plan(18);

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

select has_function(
    'public',
    'save_candidate_profile',
    array['uuid', 'jsonb'],
    'save_candidate_profile function exists'
);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'authenticated')
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then has_function_privilege('authenticated', 'public.save_candidate_profile(uuid, jsonb)', 'execute')
                  and not has_function_privilege('anon', 'public.save_candidate_profile(uuid, jsonb)', 'execute')
                 else false end),
    true,
    'authenticated has execute on save_candidate_profile and anon does not'
);

insert into auth.users (id, email)
values
    ('00000000-0000-0000-0000-000000000001', 'profile-owner@example.com'),
    ('00000000-0000-0000-0000-000000000002', 'other-profile@example.com');

insert into public.cvs (id, user_id, original_name, mime_type, storage_path, is_active, extraction_status)
values
    ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'cv1.pdf', 'application/pdf', 'path1', true, 'extracted'),
    ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'cv2.pdf', 'application/pdf', 'path2', false, 'extracted');

insert into public.search_profiles (id, user_id, is_current, title)
values
    ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', true, 'Default Search Profile');

select set_config(
    'request.jwt.claims',
    '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}',
    true
);
set local role authenticated;

select is(
    public.save_candidate_profile(
        '10000000-0000-0000-0000-000000000002'::uuid,
        '{"seniority":"mid","skills":["Python","SQL"]}'::jsonb
    ),
    1,
    'save_candidate_profile returns version 1'
);

select is(
    (select is_active from public.cvs where id = '10000000-0000-0000-0000-000000000002'),
    true,
    'target cv is now active'
);

select is(
    (select is_active from public.cvs where id = '10000000-0000-0000-0000-000000000001'),
    false,
    'previous active cv is deactivated'
);

select is(
    (select candidate_profile_id is not null from public.search_profiles where id = '20000000-0000-0000-0000-000000000001'),
    true,
    'search profile links to confirmed candidate profile'
);

select set_config(
    'request.jwt.claims',
    '{"sub":"00000000-0000-0000-0000-000000000002","role":"authenticated"}',
    true
);

select throws_ok(
    $$select public.save_candidate_profile(
        '10000000-0000-0000-0000-000000000002'::uuid,
        '{"seniority":"senior"}'::jsonb
    )$$,
    'P0001',
    'cv_not_found',
    'cross-user save_candidate_profile raises cv_not_found'
);

set local role postgres;

select * from finish();
rollback;
