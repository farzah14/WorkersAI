begin;
create extension if not exists pgtap;
select plan(167);

select is(
    (select coalesce(prosecdef, false)
     from pg_proc
     where oid = to_regprocedure(
       'public.create_manual_search_run(uuid,uuid,text,text[],text[],text[],text[],numeric,text,text[],boolean)'
     )),
    true,
    'manual search run RPC is security definer'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'service_role')
                      and exists (select 1 from pg_roles where rolname = 'anon')
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_function_privilege(
                        'service_role',
                        'public.create_manual_search_run(uuid,uuid,text,text[],text[],text[],text[],numeric,text,text[],boolean)',
                        'execute'
                      )
                   and not has_function_privilege(
                        'anon',
                        'public.create_manual_search_run(uuid,uuid,text,text[],text[],text[],text[],numeric,text,text[],boolean)',
                        'execute'
                      )
                   and not has_function_privilege(
                        'authenticated',
                        'public.create_manual_search_run(uuid,uuid,text,text[],text[],text[],text[],numeric,text,text[],boolean)',
                        'execute'
                      )
                 else false end),
    true,
    'manual search run RPC is service-role only'
);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'search_profiles'),
    1::bigint,
    'search_profiles table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'job_search_runs'),
    1::bigint,
    'job_search_runs table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'job_sources'),
    1::bigint,
    'job_sources table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'jobs'),
    1::bigint,
    'jobs table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'job_search_run_jobs'),
    1::bigint,
    'job_search_run_jobs table exists'
);

select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'search_profiles'),
    true,
    'search_profiles rls is enabled'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'job_search_runs'),
    true,
    'job_search_runs rls is enabled'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'job_sources'),
    true,
    'job_sources rls is enabled'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'job_search_run_jobs'),
    true,
    'job_search_run_jobs rls is enabled'
);

select is(
    (select count(*)
     from pg_policies
     where schemaname = 'public'
       and tablename = 'search_profiles'
       and policyname = 'search_profiles_owner_all'
       and cmd = 'ALL'
       and roles @> ARRAY['authenticated']::name[]),
    1::bigint,
    'search_profiles owner policy exists'
);
select is(
    (select count(*)
     from pg_policies
     where schemaname = 'public'
       and tablename = 'job_search_runs'
       and policyname = 'job_search_runs_owner_all'
       and cmd = 'ALL'
       and roles @> ARRAY['authenticated']::name[]),
    1::bigint,
    'job_search_runs owner policy exists'
);
select is(
    (select count(*)
     from pg_policies
     where schemaname = 'public'
       and tablename = 'job_sources'
       and policyname = 'job_sources_owner_all'
       and cmd = 'ALL'
       and roles @> ARRAY['authenticated']::name[]),
    1::bigint,
    'job_sources owner policy exists'
);
select is(
    (select count(*)
     from pg_policies
     where schemaname = 'public'
       and tablename = 'job_search_run_jobs'
       and policyname = 'job_search_run_jobs_owner_all'
       and cmd = 'ALL'
       and roles @> ARRAY['authenticated']::name[]),
    1::bigint,
    'job_search_run_jobs owner policy exists'
);

select is(
    (select case when to_regclass('public.jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.jobs', 'select')
                 else false end),
    true,
    'authenticated can select global jobs'
);
select is(
    (select case when to_regclass('public.jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then has_table_privilege('anon', 'public.jobs', 'select')
                 else false end),
    false,
    'anon cannot select global jobs'
);

select is(
    (select case when to_regclass('public.work_items') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then has_table_privilege('anon', 'public.work_items', 'select')
                 else false end),
    false,
    'anon cannot select work_items'
);
select is(
    (select case when to_regclass('public.work_items') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.work_items', 'select')
                 else false end),
    false,
    'authenticated cannot select work_items'
);
select is(
    (select case when to_regclass('public.ai_requests') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then has_table_privilege('anon', 'public.ai_requests', 'select')
                 else false end),
    false,
    'anon cannot select ai_requests'
);
select is(
    (select case when to_regclass('public.ai_requests') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.ai_requests', 'select')
                 else false end),
    false,
    'authenticated cannot select ai_requests'
);

select is(
    (select case when to_regclass('public.search_profiles') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.search_profiles', 'select,insert,update,delete')
                 else false end),
    true,
    'service_role can operate on search_profiles'
);
select is(
    (select case when to_regclass('public.job_search_runs') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_search_runs', 'select,insert,update,delete')
                 else false end),
    true,
    'service_role can operate on job_search_runs'
);
select is(
    (select case when to_regclass('public.job_sources') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_sources', 'select,insert,update,delete')
                 else false end),
    true,
    'service_role can operate on job_sources'
);
select is(
    (select case when to_regclass('public.jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.jobs', 'select,insert,update,delete')
                 else false end),
    true,
    'service_role can operate on jobs'
);
select is(
    (select case when to_regclass('public.job_search_run_jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_search_run_jobs', 'select,insert,update,delete')
                 else false end),
    true,
    'service_role can operate on job_search_run_jobs'
);

select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.jobs')
       and c.contype = 'u'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute
            where attrelid = to_regclass('public.jobs') and attname = 'fingerprint')
       ]::smallint[]),
    1::bigint,
    'jobs fingerprint is unique'
);

select is(
    (select count(*) from pg_class where oid = to_regclass('public.search_profiles_user_id_idx')),
    1::bigint,
    'search_profiles user lookup index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.search_profiles_current_user_idx')),
    1::bigint,
    'current search profile lookup index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.search_profiles_candidate_profile_id_idx')),
    1::bigint,
    'search_profiles candidate profile index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_search_runs_user_created_at_idx')),
    1::bigint,
    'job_search_runs user history index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_search_runs_search_profile_id_idx')),
    1::bigint,
    'job_search_runs search profile index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_search_runs_candidate_profile_id_idx')),
    1::bigint,
    'job_search_runs candidate profile index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_sources_search_run_id_idx')),
    1::bigint,
    'job_sources search run index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.jobs_canonical_url_idx')),
    1::bigint,
    'jobs canonical URL lookup index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.jobs_status_published_at_idx')),
    1::bigint,
    'jobs status and published index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_search_run_jobs_job_id_idx')),
    1::bigint,
    'job_search_run_jobs job index exists'
);

select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.contype = 'c'
       and position('region' in pg_get_constraintdef(c.oid)) > 0
       and position('indonesia' in pg_get_constraintdef(c.oid)) > 0
       and position('global' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'search_profiles region check exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'c'
       and position('trigger' in pg_get_constraintdef(c.oid)) > 0
       and position('manual' in pg_get_constraintdef(c.oid)) > 0
       and position('daily' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs trigger check exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'c'
       and position('status' in pg_get_constraintdef(c.oid)) > 0
       and position('queued' in pg_get_constraintdef(c.oid)) > 0
       and position('processing' in pg_get_constraintdef(c.oid)) > 0
       and position('completed' in pg_get_constraintdef(c.oid)) > 0
       and position('partial' in pg_get_constraintdef(c.oid)) > 0
       and position('failed' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs status check exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_sources')
       and c.contype = 'c'
       and position('status' in pg_get_constraintdef(c.oid)) > 0
       and position('success' in pg_get_constraintdef(c.oid)) > 0
       and position('failed' in pg_get_constraintdef(c.oid)) > 0
       and position('skipped' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_sources status check exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.jobs')
       and c.contype = 'c'
       and position('status' in pg_get_constraintdef(c.oid)) > 0
       and position('active' in pg_get_constraintdef(c.oid)) > 0
       and position('expired' in pg_get_constraintdef(c.oid)) > 0
       and position('unavailable' in pg_get_constraintdef(c.oid)) > 0
       and position('unknown' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'jobs status check exists'
);

select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id)' in pg_get_constraintdef(c.oid)) > 0
        and position('auth.users(id)' in pg_get_constraintdef(c.oid)) > 0
        and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'search_profiles user foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.contype = 'f'
       and position('FOREIGN KEY (candidate_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('candidate_profiles(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'search_profiles candidate profile foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('auth.users(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs user foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('search_profiles(id)' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs search profile foreign key exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'f'
       and position('FOREIGN KEY (candidate_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('candidate_profiles(id)' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs candidate profile foreign key exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_sources')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_run_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('job_search_runs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_sources search run foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_run_jobs')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_run_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('job_search_runs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_run_jobs search run foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_run_jobs')
       and c.contype = 'f'
       and position('FOREIGN KEY (job_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('jobs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE RESTRICT' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
     'job_search_run_jobs job foreign key restricts hard delete'
);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'job_provenance'),
    1::bigint,
    'job_provenance table exists'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'job_provenance'),
    true,
    'job_provenance rls is enabled'
);
select is(
    (select count(*)
     from pg_policies
     where schemaname = 'public'
       and tablename = 'job_provenance'
       and policyname = 'job_provenance_owner_all'
       and cmd = 'ALL'
       and roles @> ARRAY['authenticated']::name[]),
    1::bigint,
    'job_provenance owner policy exists'
);
select is(
    (select coalesce(rowsecurity, false)
     from pg_tables
     where schemaname = 'public' and tablename = 'jobs'),
    false,
    'global jobs does not use owner rls'
);

select is(
    coalesce((
        select position('auth.uid()' in qual) > 0
           and position('select auth.uid()' in lower(qual)) > 0
           and position('user_id' in qual) > 0
           and position('auth.uid()' in with_check) > 0
           and position('select auth.uid()' in lower(with_check)) > 0
           and position('user_id' in with_check) > 0
        from pg_policies
        where schemaname = 'public'
          and tablename = 'search_profiles'
          and policyname = 'search_profiles_owner_all'
    ), false),
    true,
    'search_profiles policy predicates use auth.uid ownership'
);
select is(
    coalesce((
        select position('auth.uid()' in qual) > 0
           and position('select auth.uid()' in lower(qual)) > 0
           and position('user_id' in qual) > 0
           and position('auth.uid()' in with_check) > 0
           and position('select auth.uid()' in lower(with_check)) > 0
           and position('user_id' in with_check) > 0
        from pg_policies
        where schemaname = 'public'
          and tablename = 'job_search_runs'
          and policyname = 'job_search_runs_owner_all'
    ), false),
    true,
    'job_search_runs policy predicates use auth.uid ownership'
);
select is(
    coalesce((
        select position('auth.uid()' in qual) > 0
           and position('select auth.uid()' in lower(qual)) > 0
           and position('job_search_runs' in qual) > 0
           and position('user_id' in qual) > 0
           and position('auth.uid()' in with_check) > 0
           and position('select auth.uid()' in lower(with_check)) > 0
           and position('job_search_runs' in with_check) > 0
           and position('user_id' in with_check) > 0
        from pg_policies
        where schemaname = 'public'
          and tablename = 'job_sources'
          and policyname = 'job_sources_owner_all'
    ), false),
    true,
    'job_sources policy predicates use parent run ownership'
);
select is(
    coalesce((
        select position('auth.uid()' in qual) > 0
           and position('select auth.uid()' in lower(qual)) > 0
           and position('job_search_runs' in qual) > 0
           and position('user_id' in qual) > 0
           and position('auth.uid()' in with_check) > 0
           and position('select auth.uid()' in lower(with_check)) > 0
           and position('job_search_runs' in with_check) > 0
           and position('user_id' in with_check) > 0
        from pg_policies
        where schemaname = 'public'
          and tablename = 'job_search_run_jobs'
          and policyname = 'job_search_run_jobs_owner_all'
    ), false),
    true,
    'job_search_run_jobs policy predicates use parent run ownership'
);
select is(
    coalesce((
        select position('auth.uid()' in qual) > 0
           and position('select auth.uid()' in lower(qual)) > 0
           and position('job_search_runs' in qual) > 0
           and position('user_id' in qual) > 0
           and position('auth.uid()' in with_check) > 0
           and position('select auth.uid()' in lower(with_check)) > 0
           and position('job_search_runs' in with_check) > 0
           and position('user_id' in with_check) > 0
        from pg_policies
        where schemaname = 'public'
          and tablename = 'job_provenance'
          and policyname = 'job_provenance_owner_all'
    ), false),
    true,
    'job_provenance policy predicates use parent run ownership'
);

select is(
    (select case when to_regclass('public.search_profiles') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                  then has_table_privilege('authenticated', 'public.search_profiles', 'select')
                   and not has_table_privilege('authenticated', 'public.search_profiles', 'insert')
                   and not has_table_privilege('authenticated', 'public.search_profiles', 'update')
                   and not has_table_privilege('authenticated', 'public.search_profiles', 'delete')
                   and not has_table_privilege('authenticated', 'public.search_profiles', 'truncate')
                   and not has_table_privilege('authenticated', 'public.search_profiles', 'references')
                   and not has_table_privilege('authenticated', 'public.search_profiles', 'trigger')
                 else false end),
    true,
    'authenticated has exact search_profiles privileges'
);
select is(
    (select case when to_regclass('public.job_search_runs') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                  then has_table_privilege('authenticated', 'public.job_search_runs', 'select')
                   and not has_table_privilege('authenticated', 'public.job_search_runs', 'insert')
                   and not has_table_privilege('authenticated', 'public.job_search_runs', 'update')
                   and not has_table_privilege('authenticated', 'public.job_search_runs', 'delete')
                   and not has_table_privilege('authenticated', 'public.job_search_runs', 'truncate')
                   and not has_table_privilege('authenticated', 'public.job_search_runs', 'references')
                   and not has_table_privilege('authenticated', 'public.job_search_runs', 'trigger')
                 else false end),
    true,
    'authenticated has exact job_search_runs privileges'
);
select is(
    (select case when to_regclass('public.job_sources') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.job_sources', 'select')
                   and not has_table_privilege('authenticated', 'public.job_sources', 'insert')
                   and not has_table_privilege('authenticated', 'public.job_sources', 'update')
                   and not has_table_privilege('authenticated', 'public.job_sources', 'delete')
                   and not has_table_privilege('authenticated', 'public.job_sources', 'truncate')
                   and not has_table_privilege('authenticated', 'public.job_sources', 'references')
                   and not has_table_privilege('authenticated', 'public.job_sources', 'trigger')
                 else false end),
    true,
    'authenticated has exact job_sources privileges'
);
select is(
    (select case when to_regclass('public.job_search_run_jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.job_search_run_jobs', 'select')
                   and not has_table_privilege('authenticated', 'public.job_search_run_jobs', 'insert')
                   and not has_table_privilege('authenticated', 'public.job_search_run_jobs', 'update')
                   and not has_table_privilege('authenticated', 'public.job_search_run_jobs', 'delete')
                   and not has_table_privilege('authenticated', 'public.job_search_run_jobs', 'truncate')
                   and not has_table_privilege('authenticated', 'public.job_search_run_jobs', 'references')
                   and not has_table_privilege('authenticated', 'public.job_search_run_jobs', 'trigger')
                 else false end),
    true,
    'authenticated has exact job_search_run_jobs privileges'
);
select is(
    (select case when to_regclass('public.jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.jobs', 'select')
                   and not has_table_privilege('authenticated', 'public.jobs', 'insert')
                   and not has_table_privilege('authenticated', 'public.jobs', 'update')
                   and not has_table_privilege('authenticated', 'public.jobs', 'delete')
                   and not has_table_privilege('authenticated', 'public.jobs', 'truncate')
                   and not has_table_privilege('authenticated', 'public.jobs', 'references')
                   and not has_table_privilege('authenticated', 'public.jobs', 'trigger')
                 else false end),
    true,
    'authenticated has exact jobs privileges'
);
select is(
    (select case when to_regclass('public.job_provenance') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then has_table_privilege('authenticated', 'public.job_provenance', 'select')
                   and not has_table_privilege('authenticated', 'public.job_provenance', 'insert')
                   and not has_table_privilege('authenticated', 'public.job_provenance', 'update')
                   and not has_table_privilege('authenticated', 'public.job_provenance', 'delete')
                   and not has_table_privilege('authenticated', 'public.job_provenance', 'truncate')
                   and not has_table_privilege('authenticated', 'public.job_provenance', 'references')
                   and not has_table_privilege('authenticated', 'public.job_provenance', 'trigger')
                 else false end),
    true,
    'authenticated has exact job_provenance privileges'
);

select is(
    (select case when to_regclass('public.search_profiles') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.search_profiles', 'select')
                   and not has_table_privilege('anon', 'public.search_profiles', 'insert')
                   and not has_table_privilege('anon', 'public.search_profiles', 'update')
                   and not has_table_privilege('anon', 'public.search_profiles', 'delete')
                   and not has_table_privilege('anon', 'public.search_profiles', 'truncate')
                   and not has_table_privilege('anon', 'public.search_profiles', 'references')
                   and not has_table_privilege('anon', 'public.search_profiles', 'trigger')
                 else false end),
    true,
    'anon has no search_profiles access'
);
select is(
    (select case when to_regclass('public.job_search_runs') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.job_search_runs', 'select')
                   and not has_table_privilege('anon', 'public.job_search_runs', 'insert')
                   and not has_table_privilege('anon', 'public.job_search_runs', 'update')
                   and not has_table_privilege('anon', 'public.job_search_runs', 'delete')
                   and not has_table_privilege('anon', 'public.job_search_runs', 'truncate')
                   and not has_table_privilege('anon', 'public.job_search_runs', 'references')
                   and not has_table_privilege('anon', 'public.job_search_runs', 'trigger')
                 else false end),
    true,
    'anon has no job_search_runs access'
);
select is(
    (select case when to_regclass('public.job_sources') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.job_sources', 'select')
                   and not has_table_privilege('anon', 'public.job_sources', 'insert')
                   and not has_table_privilege('anon', 'public.job_sources', 'update')
                   and not has_table_privilege('anon', 'public.job_sources', 'delete')
                   and not has_table_privilege('anon', 'public.job_sources', 'truncate')
                   and not has_table_privilege('anon', 'public.job_sources', 'references')
                   and not has_table_privilege('anon', 'public.job_sources', 'trigger')
                 else false end),
    true,
    'anon has no job_sources access'
);
select is(
    (select case when to_regclass('public.job_search_run_jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.job_search_run_jobs', 'select')
                   and not has_table_privilege('anon', 'public.job_search_run_jobs', 'insert')
                   and not has_table_privilege('anon', 'public.job_search_run_jobs', 'update')
                   and not has_table_privilege('anon', 'public.job_search_run_jobs', 'delete')
                   and not has_table_privilege('anon', 'public.job_search_run_jobs', 'truncate')
                   and not has_table_privilege('anon', 'public.job_search_run_jobs', 'references')
                   and not has_table_privilege('anon', 'public.job_search_run_jobs', 'trigger')
                 else false end),
    true,
    'anon has no job_search_run_jobs access'
);
select is(
    (select case when to_regclass('public.jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.jobs', 'select')
                   and not has_table_privilege('anon', 'public.jobs', 'insert')
                   and not has_table_privilege('anon', 'public.jobs', 'update')
                   and not has_table_privilege('anon', 'public.jobs', 'delete')
                   and not has_table_privilege('anon', 'public.jobs', 'truncate')
                   and not has_table_privilege('anon', 'public.jobs', 'references')
                   and not has_table_privilege('anon', 'public.jobs', 'trigger')
                 else false end),
    true,
    'anon has no jobs access'
);
select is(
    (select case when to_regclass('public.job_provenance') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.job_provenance', 'select')
                   and not has_table_privilege('anon', 'public.job_provenance', 'insert')
                   and not has_table_privilege('anon', 'public.job_provenance', 'update')
                   and not has_table_privilege('anon', 'public.job_provenance', 'delete')
                   and not has_table_privilege('anon', 'public.job_provenance', 'truncate')
                   and not has_table_privilege('anon', 'public.job_provenance', 'references')
                   and not has_table_privilege('anon', 'public.job_provenance', 'trigger')
                 else false end),
    true,
    'anon has no job_provenance access'
);
select is(
    (select case when to_regclass('public.work_items') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.work_items', 'select')
                   and not has_table_privilege('anon', 'public.work_items', 'insert')
                   and not has_table_privilege('anon', 'public.work_items', 'update')
                   and not has_table_privilege('anon', 'public.work_items', 'delete')
                 else false end),
    true,
    'anon has no work_items access'
);
select is(
    (select case when to_regclass('public.ai_requests') is not null
                      and exists (select 1 from pg_roles where rolname = 'anon')
                 then not has_table_privilege('anon', 'public.ai_requests', 'select')
                   and not has_table_privilege('anon', 'public.ai_requests', 'insert')
                   and not has_table_privilege('anon', 'public.ai_requests', 'update')
                   and not has_table_privilege('anon', 'public.ai_requests', 'delete')
                 else false end),
    true,
    'anon has no ai_requests access'
);
select is(
    (select case when to_regclass('public.work_items') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then not has_table_privilege('authenticated', 'public.work_items', 'select')
                   and not has_table_privilege('authenticated', 'public.work_items', 'insert')
                   and not has_table_privilege('authenticated', 'public.work_items', 'update')
                   and not has_table_privilege('authenticated', 'public.work_items', 'delete')
                   and not has_table_privilege('authenticated', 'public.work_items', 'truncate')
                   and not has_table_privilege('authenticated', 'public.work_items', 'references')
                   and not has_table_privilege('authenticated', 'public.work_items', 'trigger')
                 else false end),
    true,
    'authenticated has no work_items access'
);
select is(
    (select case when to_regclass('public.ai_requests') is not null
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                 then not has_table_privilege('authenticated', 'public.ai_requests', 'select')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'insert')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'update')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'delete')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'truncate')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'references')
                   and not has_table_privilege('authenticated', 'public.ai_requests', 'trigger')
                 else false end),
    true,
    'authenticated has no ai_requests access'
);

select is(
    (select case when to_regclass('public.search_profiles') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.search_profiles', 'select')
                   and has_table_privilege('service_role', 'public.search_profiles', 'insert')
                   and has_table_privilege('service_role', 'public.search_profiles', 'update')
                   and has_table_privilege('service_role', 'public.search_profiles', 'delete')
                 else false end),
    true,
    'service_role can operate on search_profiles'
);
select is(
    (select case when to_regclass('public.job_search_runs') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_search_runs', 'select')
                   and has_table_privilege('service_role', 'public.job_search_runs', 'insert')
                   and has_table_privilege('service_role', 'public.job_search_runs', 'update')
                   and has_table_privilege('service_role', 'public.job_search_runs', 'delete')
                 else false end),
    true,
    'service_role can operate on job_search_runs'
);
select is(
    (select case when to_regclass('public.job_sources') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_sources', 'select')
                   and has_table_privilege('service_role', 'public.job_sources', 'insert')
                   and has_table_privilege('service_role', 'public.job_sources', 'update')
                   and has_table_privilege('service_role', 'public.job_sources', 'delete')
                 else false end),
    true,
    'service_role can operate on job_sources'
);
select is(
    (select case when to_regclass('public.jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.jobs', 'select')
                   and has_table_privilege('service_role', 'public.jobs', 'insert')
                   and has_table_privilege('service_role', 'public.jobs', 'update')
                   and has_table_privilege('service_role', 'public.jobs', 'delete')
                 else false end),
    true,
    'service_role can operate on jobs'
);
select is(
    (select case when to_regclass('public.job_search_run_jobs') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_search_run_jobs', 'select')
                   and has_table_privilege('service_role', 'public.job_search_run_jobs', 'insert')
                   and has_table_privilege('service_role', 'public.job_search_run_jobs', 'update')
                   and has_table_privilege('service_role', 'public.job_search_run_jobs', 'delete')
                 else false end),
    true,
    'service_role can operate on job_search_run_jobs'
);
select is(
    (select case when to_regclass('public.job_provenance') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_provenance', 'select')
                   and has_table_privilege('service_role', 'public.job_provenance', 'insert')
                   and has_table_privilege('service_role', 'public.job_provenance', 'update')
                   and has_table_privilege('service_role', 'public.job_provenance', 'delete')
                 else false end),
    true,
    'service_role can operate on job_provenance'
);
select is(
    (select case when to_regclass('public.work_items') is not null
                      and to_regclass('public.ai_requests') is not null
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.work_items', 'select')
                   and has_table_privilege('service_role', 'public.work_items', 'insert')
                   and has_table_privilege('service_role', 'public.work_items', 'update')
                   and has_table_privilege('service_role', 'public.work_items', 'delete')
                   and has_table_privilege('service_role', 'public.ai_requests', 'select')
                   and has_table_privilege('service_role', 'public.ai_requests', 'insert')
                   and has_table_privilege('service_role', 'public.ai_requests', 'update')
                   and has_table_privilege('service_role', 'public.ai_requests', 'delete')
                 else false end),
    true,
    'service_role can operate on worker-only tables'
);

select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'search_profiles'
       and column_name = any (array[
           'id','user_id','candidate_profile_id','region','target_roles','locations',
           'work_modes','employment_types','excluded_keywords','daily_enabled',
           'is_current','created_at'])
       and is_nullable = 'NO'),
    12::bigint,
    'search_profiles critical columns are present and not null'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_search_runs'
       and column_name = any (array[
           'id','user_id','search_profile_id','candidate_profile_id','trigger','status',
           'discovered_count','normalized_count','duplicate_count','failed_count','created_at'])
       and is_nullable = 'NO'),
    11::bigint,
    'job_search_runs critical columns are present and not null'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_sources'
       and column_name = any (array[
           'id','search_run_id','source_type','source_key','status','result_count','created_at'])
       and is_nullable = 'NO'),
    7::bigint,
    'job_sources critical columns are present and not null'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'jobs'
       and column_name = any (array[
           'id','fingerprint','title','company','description','source_name',
           'original_url','canonical_url','first_seen_at','last_seen_at',
           'last_checked_at','region','status'])
       and is_nullable = 'NO'),
    13::bigint,
    'jobs critical columns are present and not null'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_search_run_jobs'
       and column_name = any (array['search_run_id','job_id'])
       and is_nullable = 'NO'),
    2::bigint,
    'job_search_run_jobs key columns are present and not null'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_provenance'
       and column_name = any (array[
           'id','job_id','search_run_id','source_type','source_key',
           'original_url','canonical_url','created_at'])
       and is_nullable = 'NO'),
    8::bigint,
    'job_provenance critical columns are present and not null'
);

select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'search_profiles'
       and (
         (column_name = 'id' and position('gen_random_uuid()' in column_default) > 0)
         or (column_name in ('locations','work_modes','excluded_keywords') and column_default is not null)
         or (column_name = 'employment_types' and position('full-time' in column_default) > 0)
         or (column_name = 'daily_enabled' and position('false' in column_default) > 0)
         or (column_name = 'is_current' and position('true' in column_default) > 0)
         or (column_name = 'created_at' and position('now()' in column_default) > 0)
       )),
    8::bigint,
    'search_profiles critical defaults exist'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_search_runs'
       and (
         (column_name = 'id' and position('gen_random_uuid()' in column_default) > 0)
         or (column_name = 'status' and position('queued' in column_default) > 0)
         or (column_name in ('discovered_count','normalized_count','duplicate_count','failed_count')
             and position('0' in column_default) > 0)
         or (column_name = 'created_at' and position('now()' in column_default) > 0)
       )),
    7::bigint,
    'job_search_runs critical defaults exist'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_sources'
       and (
         (column_name = 'id' and position('gen_random_uuid()' in column_default) > 0)
         or (column_name = 'status' and position('queued' in column_default) > 0)
         or (column_name = 'result_count' and position('0' in column_default) > 0)
         or (column_name = 'created_at' and position('now()' in column_default) > 0)
       )),
    4::bigint,
    'job_sources critical defaults exist'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'jobs'
       and (
         (column_name = 'id' and position('gen_random_uuid()' in column_default) > 0)
         or (column_name = 'status' and position('active' in column_default) > 0)
         or (column_name in ('first_seen_at','last_seen_at') and position('now()' in column_default) > 0)
         or (column_name = 'last_checked_at' and position('now()' in column_default) > 0)
         or (column_name = 'region' and position('unknown' in column_default) > 0)
       )),
    6::bigint,
    'jobs critical defaults exist'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_provenance'
       and (
         (column_name = 'id' and position('gen_random_uuid()' in column_default) > 0)
         or (column_name = 'created_at' and position('now()' in column_default) > 0)
       )),
    2::bigint,
    'job_provenance critical defaults exist'
);

select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.candidate_profiles')
       and c.conname = 'candidate_profiles_user_id_id_key'
       and c.contype = 'u'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute where attrelid = to_regclass('public.candidate_profiles') and attname = 'user_id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.candidate_profiles') and attname = 'id')
       ]::smallint[]),
    1::bigint,
    'candidate_profiles has composite user and id key'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.cvs')
       and c.conname = 'cvs_user_id_id_key'
       and c.contype = 'u'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute where attrelid = to_regclass('public.cvs') and attname = 'user_id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.cvs') and attname = 'id')
       ]::smallint[]),
    1::bigint,
    'cvs has composite user and id key'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.candidate_profiles')
       and c.conname = 'candidate_profiles_user_cv_fk'
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id, cv_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('cvs(user_id, id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'candidate_profiles enforces CV ownership with a composite foreign key'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.conname = 'search_profiles_user_id_id_key'
       and c.contype = 'u'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute where attrelid = to_regclass('public.search_profiles') and attname = 'user_id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.search_profiles') and attname = 'id')
       ]::smallint[]),
    1::bigint,
    'search_profiles has composite user and id key'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.conname = 'search_profiles_id_candidate_profile_id_key'
       and c.contype = 'u'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute where attrelid = to_regclass('public.search_profiles') and attname = 'id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.search_profiles') and attname = 'candidate_profile_id')
       ]::smallint[]),
    1::bigint,
    'search_profiles has composite id and candidate profile key'
);
select is(
    (select coalesce((indisunique and indpred is not null
                      and position('is_current' in pg_get_expr(indpred, indrelid)) > 0), false)
     from pg_index
     where indexrelid = to_regclass('public.search_profiles_current_user_idx')),
    true,
    'current search profile index is unique and partial'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_sources')
       and c.conname = 'job_sources_run_source_key_key'
       and c.contype = 'u'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_sources') and attname = 'search_run_id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_sources') and attname = 'source_type'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_sources') and attname = 'source_key')
       ]::smallint[]),
    1::bigint,
    'job_sources is idempotent per run and source identity'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_provenance')
       and c.conname = 'job_provenance_run_job_source_key'
       and c.contype = 'u'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_provenance') and attname = 'search_run_id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_provenance') and attname = 'job_id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_provenance') and attname = 'source_type'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_provenance') and attname = 'source_key')
       ]::smallint[]),
    1::bigint,
    'job_provenance is idempotent per run, job, and source identity'
);
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                      and exists (select 1 from pg_roles where rolname = 'service_role')
                      and exists (select 1 from pg_roles where rolname = 'postgres')
                 then not has_function_privilege('anon', 'public.text_array_has_no_blank_elements(text[])', 'execute')
                   and not has_function_privilege('authenticated', 'public.text_array_has_no_blank_elements(text[])', 'execute')
                   and has_function_privilege('service_role', 'public.text_array_has_no_blank_elements(text[])', 'execute')
                   and has_function_privilege('postgres', 'public.text_array_has_no_blank_elements(text[])', 'execute')
                 else false end),
    true,
    'target role helper has server-only execute privileges'
);
select is(
    (select not exists (
        select 1
        from pg_default_acl d
        cross join lateral aclexplode(coalesce(d.defaclacl, '{}'::aclitem[])) as grants
        left join pg_roles r on r.oid = grants.grantee
        where d.defaclrole = 'postgres'::regrole
          and d.defaclnamespace = 'public'::regnamespace
          and d.defaclobjtype in ('r','f')
          and (grants.grantee = 0 or r.rolname in ('anon','authenticated'))
    )),
    true,
    'public default table and function privileges exclude browser roles'
);
select is(
    (select not exists (
        select 1
        from pg_default_acl d
        cross join lateral aclexplode(coalesce(d.defaclacl, '{}'::aclitem[])) as grants
        left join pg_roles r on r.oid = grants.grantee
        where d.defaclrole = 'postgres'::regrole
          and d.defaclnamespace = 'public'::regnamespace
          and d.defaclobjtype = 'S'
          and (grants.grantee = 0 or r.rolname in ('anon','authenticated'))
          and grants.privilege_type in ('USAGE','SELECT','UPDATE')
    )),
    true,
    'public default sequence privileges exclude browser roles'
);
select is(
    (select not exists (
        select 1
        from pg_default_acl d
        cross join lateral aclexplode(coalesce(d.defaclacl, '{}'::aclitem[])) as grants
        left join pg_roles r on r.oid = grants.grantee
        where d.defaclrole = 'postgres'::regrole
          and d.defaclnamespace = 0
          and d.defaclobjtype in ('f','S')
          and (grants.grantee = 0 or r.rolname in ('anon','authenticated'))
          and ((d.defaclobjtype = 'f' and grants.privilege_type = 'EXECUTE')
            or (d.defaclobjtype = 'S' and grants.privilege_type in ('USAGE','SELECT','UPDATE')))
    )),
    true,
    'global default function and sequence privileges exclude browser roles'
);
create function public.pgtap_default_function_probe()
returns void
language sql
as $$
  select 1;
$$;
create sequence public.pgtap_default_sequence_probe;
select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                      and exists (select 1 from pg_roles where rolname = 'authenticated')
                      and exists (select 1 from pg_roles where rolname = 'postgres')
                 then not has_function_privilege('anon', 'public.pgtap_default_function_probe()', 'execute')
                   and not has_function_privilege('authenticated', 'public.pgtap_default_function_probe()', 'execute')
                   and has_function_privilege('postgres', 'public.pgtap_default_function_probe()', 'execute')
                   and not has_sequence_privilege('anon', 'public.pgtap_default_sequence_probe', 'usage')
                   and not has_sequence_privilege('anon', 'public.pgtap_default_sequence_probe', 'select')
                   and not has_sequence_privilege('anon', 'public.pgtap_default_sequence_probe', 'update')
                   and not has_sequence_privilege('authenticated', 'public.pgtap_default_sequence_probe', 'usage')
                   and not has_sequence_privilege('authenticated', 'public.pgtap_default_sequence_probe', 'select')
                   and not has_sequence_privilege('authenticated', 'public.pgtap_default_sequence_probe', 'update')
                   and has_sequence_privilege('postgres', 'public.pgtap_default_sequence_probe', 'usage')
                 else false end),
    true,
    'future public functions and sequences exclude browser privileges'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_run_jobs')
       and c.contype = 'p'
       and c.conkey = ARRAY[
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_search_run_jobs') and attname = 'search_run_id'),
           (select attnum from pg_attribute where attrelid = to_regclass('public.job_search_run_jobs') and attname = 'job_id')
       ]::smallint[]),
    1::bigint,
    'job_search_run_jobs has a composite primary key'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_provenance_job_id_idx')),
    1::bigint,
    'job_provenance job lookup index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.candidate_profiles_user_cv_idx')),
    1::bigint,
    'candidate_profiles composite CV lookup index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.search_profiles_user_candidate_profile_idx')),
    1::bigint,
    'search_profiles composite ownership index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_search_runs_user_search_profile_idx')),
    1::bigint,
    'job_search_runs user search profile index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_search_runs_user_candidate_profile_idx')),
    1::bigint,
    'job_search_runs user candidate profile index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_search_runs_search_profile_candidate_profile_idx')),
    1::bigint,
    'job_search_runs search profile candidate profile index exists'
);
select is(
    (select count(*) from pg_class where oid = to_regclass('public.job_provenance_search_run_source_idx')),
    1::bigint,
    'job_provenance source lookup index exists'
);

select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.conname = 'search_profiles_target_roles_non_empty_check'
       and c.contype = 'c'
        and position('text_array_has_no_blank_elements' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'search_profiles requires a non-empty target_roles array'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.conname = 'search_profiles_work_modes_check'
       and c.contype = 'c'
       and position('remote' in pg_get_constraintdef(c.oid)) > 0
       and position('hybrid' in pg_get_constraintdef(c.oid)) > 0
       and position('on-site' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'search_profiles work_modes are constrained'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.conname = 'search_profiles_min_salary_check'
       and c.contype = 'c'
       and position('min_salary' in pg_get_constraintdef(c.oid)) > 0
       and position('>=' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'search_profiles min_salary cannot be negative'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.conname = 'job_search_runs_counts_non_negative_check'
       and c.contype = 'c'
       and position('discovered_count' in pg_get_constraintdef(c.oid)) > 0
       and position('normalized_count' in pg_get_constraintdef(c.oid)) > 0
       and position('duplicate_count' in pg_get_constraintdef(c.oid)) > 0
       and position('failed_count' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs counters cannot be negative'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_sources')
       and c.conname = 'job_sources_result_count_non_negative_check'
       and c.contype = 'c'
       and position('result_count' in pg_get_constraintdef(c.oid)) > 0
       and position('>= 0' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_sources result_count cannot be negative'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.jobs')
       and c.conname = 'jobs_salary_bounds_check'
       and c.contype = 'c'
       and position('salary_min' in pg_get_constraintdef(c.oid)) > 0
       and position('salary_max' in pg_get_constraintdef(c.oid)) > 0
       and position('>=' in pg_get_constraintdef(c.oid)) > 0
       and position('<=' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'jobs salary bounds are sane'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.jobs')
       and c.conname = 'jobs_required_text_non_empty_check'
       and c.contype = 'c'
       and position('title' in pg_get_constraintdef(c.oid)) > 0
       and position('company' in pg_get_constraintdef(c.oid)) > 0
       and position('description' in pg_get_constraintdef(c.oid)) > 0
       and position('original_url' in pg_get_constraintdef(c.oid)) > 0
       and position('canonical_url' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'jobs required text and URLs cannot be empty'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.jobs')
       and c.conname = 'jobs_work_mode_check'
       and c.contype = 'c'
       and position('remote' in pg_get_constraintdef(c.oid)) > 0
       and position('hybrid' in pg_get_constraintdef(c.oid)) > 0
       and position('on-site' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'jobs work_mode is constrained when present'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.jobs')
       and c.conname = 'jobs_region_check'
       and c.contype = 'c'
       and position('indonesia' in pg_get_constraintdef(c.oid)) > 0
       and position('global' in pg_get_constraintdef(c.oid)) > 0
       and position('unknown' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'jobs region has a bounded normalized value set'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.jobs')
       and c.conname = 'jobs_fingerprint_non_empty_check'
       and c.contype = 'c'
       and position('fingerprint' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'jobs fingerprint cannot be empty'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_provenance')
       and c.conname = 'job_provenance_required_text_non_empty_check'
       and c.contype = 'c'
       and position('source_type' in pg_get_constraintdef(c.oid)) > 0
       and position('source_key' in pg_get_constraintdef(c.oid)) > 0
       and position('original_url' in pg_get_constraintdef(c.oid)) > 0
       and position('canonical_url' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_provenance source identity and URLs cannot be empty'
);

select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.search_profiles')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id, candidate_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('candidate_profiles(user_id, id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'search_profiles enforces candidate profile ownership with a composite foreign key'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id, search_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('search_profiles(user_id, id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs enforces search profile ownership with a composite foreign key'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id, candidate_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('candidate_profiles(user_id, id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs enforces candidate profile ownership with a composite foreign key'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_search_runs')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_profile_id, candidate_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('search_profiles(id, candidate_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_search_runs candidate matches its search profile'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_provenance')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_run_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('job_search_runs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_provenance links to search runs with cascade'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_provenance')
       and c.contype = 'f'
       and position('FOREIGN KEY (job_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('jobs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE RESTRICT' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_provenance job foreign key restricts hard delete'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_provenance')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_run_id, job_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('job_search_run_jobs(search_run_id, job_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_provenance is constrained to discovered run jobs'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_sources')
       and c.conname = 'job_sources_required_text_non_empty_check'
       and c.contype = 'c'
       and position('btrim(source_type)' in pg_get_constraintdef(c.oid)) > 0
       and position('btrim(source_key)' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_sources source identity fields cannot be blank'
);

insert into auth.users (id, email)
values ('00000000-0000-0000-0000-000000000001', 'job-discovery-fixture@example.test');
insert into auth.users (id, email)
values ('00000000-0000-0000-0000-000000000002', 'job-discovery-fixture-b@example.test');

set local role service_role;
insert into public.cvs (id, user_id, original_name, mime_type)
values
  ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000001', 'fixture-a.pdf', 'application/pdf'),
  ('00000000-0000-0000-0000-000000000102', '00000000-0000-0000-0000-000000000001', 'fixture-b.pdf', 'application/pdf');

insert into public.candidate_profiles (id, user_id, cv_id, version, profile)
values
  ('00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 1, '{}'::jsonb),
  ('00000000-0000-0000-0000-000000000202', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000102', 1, '{}'::jsonb);

insert into public.search_profiles (id, user_id, candidate_profile_id, region, target_roles)
values ('00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000201', 'indonesia', ARRAY['Data Engineer']);

select throws_ok(
    $$
      insert into public.search_profiles (id, user_id, candidate_profile_id, region, target_roles, is_current)
      values ('00000000-0000-0000-0000-000000000303', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000201', 'indonesia', ARRAY[''], false)
    $$,
    '23514',
    null,
    'rejects an empty target role element'
);
delete from public.search_profiles
where id = '00000000-0000-0000-0000-000000000303';

select throws_ok(
    $$
      insert into public.search_profiles (id, user_id, candidate_profile_id, region, target_roles, is_current)
      values ('00000000-0000-0000-0000-000000000304', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000201', 'indonesia', ARRAY['   '], false)
    $$,
    '23514',
    null,
    'rejects a whitespace-only target role element'
);
delete from public.search_profiles
where id = '00000000-0000-0000-0000-000000000304';

insert into public.job_search_runs (id, user_id, search_profile_id, candidate_profile_id, trigger)
values ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000201', 'manual');

insert into public.jobs (id, fingerprint, title, company, description, source_name, original_url, canonical_url)
values ('00000000-0000-0000-0000-000000000501', 'fixture-fingerprint', 'Data Engineer', 'Fixture Co', 'Fixture description', 'fixture', 'https://example.test/jobs/1', 'https://example.test/jobs/1');

insert into public.job_search_run_jobs (search_run_id, job_id)
values ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000501');

insert into public.job_sources (search_run_id, source_type, source_key)
values ('00000000-0000-0000-0000-000000000401', 'greenhouse', 'board-a');

insert into public.job_provenance (job_id, search_run_id, source_type, source_key, original_url, canonical_url)
values ('00000000-0000-0000-0000-000000000501', '00000000-0000-0000-0000-000000000401', 'greenhouse', 'board-a', 'https://example.test/jobs/1', 'https://example.test/jobs/1');
insert into public.cvs (id, user_id, original_name, mime_type)
values ('00000000-0000-0000-0000-000000000103', '00000000-0000-0000-0000-000000000002', 'fixture-b-user.pdf', 'application/pdf');

insert into public.candidate_profiles (id, user_id, cv_id, version, profile)
values ('00000000-0000-0000-0000-000000000203', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000103', 1, '{}'::jsonb);

insert into public.search_profiles (id, user_id, candidate_profile_id, region, target_roles)
values ('00000000-0000-0000-0000-000000000302', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000203', 'global', ARRAY['Platform Engineer']);

insert into public.job_search_runs (id, user_id, search_profile_id, candidate_profile_id, trigger)
values ('00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000302', '00000000-0000-0000-0000-000000000203', 'manual');

insert into public.jobs (id, fingerprint, title, company, description, source_name, original_url, canonical_url)
values ('00000000-0000-0000-0000-000000000502', 'fixture-fingerprint-b', 'Platform Engineer', 'Fixture B Co', 'Fixture B description', 'fixture-b', 'https://example.test/jobs/2', 'https://example.test/jobs/2');

insert into public.job_search_run_jobs (search_run_id, job_id)
values ('00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000502');

insert into public.job_sources (search_run_id, source_type, source_key)
values ('00000000-0000-0000-0000-000000000403', 'lever', 'board-b');

insert into public.job_provenance (job_id, search_run_id, source_type, source_key, original_url, canonical_url)
values ('00000000-0000-0000-0000-000000000502', '00000000-0000-0000-0000-000000000403', 'lever', 'board-b', 'https://example.test/jobs/2', 'https://example.test/jobs/2');

update public.cvs
set is_active = true
where id = '00000000-0000-0000-0000-000000000101';
update public.candidate_profiles
set confirmed_at = now()
where id = '00000000-0000-0000-0000-000000000201';

delete from public.work_items where kind = 'discover_jobs';

select lives_ok(
    $$
      select * from public.create_manual_search_run(
        '00000000-0000-0000-0000-000000000001'::uuid,
        '00000000-0000-0000-0000-000000000201'::uuid,
        'indonesia',
        ARRAY['Data Engineer']::text[],
        ARRAY['Jakarta']::text[],
        ARRAY['hybrid']::text[],
        ARRAY['full-time']::text[],
        10000000,
        'IDR',
        ARRAY['sales']::text[],
        false
      )
    $$,
    'service role can create a manual search run through the RPC'
);

select is(
    (select case when (select is_current from public.search_profiles where id = '00000000-0000-0000-0000-000000000301') = false
                      and (select count(*) from public.search_profiles
                           where user_id = '00000000-0000-0000-0000-000000000001'
                             and is_current) = 1
                      and (select count(*) from public.job_search_runs
                           where user_id = '00000000-0000-0000-0000-000000000001'
                             and trigger = 'manual') = 2
                      and (select count(*) from public.work_items
                           where kind = 'discover_jobs'
                             and dedupe_key like 'discover_jobs:%') = 1
                 then true else false end),
    true,
    'manual search RPC atomically rotates the current profile, creates a run, and enqueues discovery'
);
reset role;

select throws_ok(
    $$
      insert into public.candidate_profiles (id, user_id, cv_id, version, profile)
      values ('00000000-0000-0000-0000-000000000204', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000103', 2, '{}'::jsonb)
    $$,
    '23503',
    null,
    'rejects a candidate profile that references another user CV'
);
delete from public.candidate_profiles
where id = '00000000-0000-0000-0000-000000000204';

select throws_ok(
    $$
      insert into public.job_search_runs (id, user_id, search_profile_id, candidate_profile_id, trigger)
      values ('00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000202', 'manual')
    $$,
    '23503',
    null,
    'rejects a run whose candidate differs from its search profile'
);
delete from public.job_search_runs
where id = '00000000-0000-0000-0000-000000000402';

select throws_ok(
    $$
      insert into public.job_provenance (job_id, search_run_id, source_type, source_key, original_url, canonical_url)
      values ('00000000-0000-0000-0000-000000000501', '00000000-0000-0000-0000-000000000401', 'lever', 'missing', 'https://example.test/jobs/1', 'https://example.test/jobs/1')
    $$,
    '23503',
    null,
    'rejects provenance without a matching source row'
);
delete from public.job_provenance
where search_run_id = '00000000-0000-0000-0000-000000000401'
  and source_type = 'lever'
  and source_key = 'missing';

select throws_ok(
    $$
      insert into public.job_sources (search_run_id, source_type, source_key)
      values ('00000000-0000-0000-0000-000000000401', 'greenhouse', 'board-a')
    $$,
    '23505',
    null,
    'rejects a duplicate source identity within a run'
);

select throws_ok(
    $$
      insert into public.job_provenance (job_id, search_run_id, source_type, source_key, original_url, canonical_url)
      values ('00000000-0000-0000-0000-000000000501', '00000000-0000-0000-0000-000000000401', 'greenhouse', 'board-a', 'https://example.test/jobs/1', 'https://example.test/jobs/1')
    $$,
    '23505',
    null,
    'rejects duplicate provenance for the same source identity'
);

-- Behavioral RLS visibility isolation; fixtures above were written by service_role.
grant insert, update, delete on public.search_profiles, public.job_search_runs,
  public.job_sources, public.job_search_run_jobs, public.job_provenance
  to authenticated;
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001"}', true);

select is((select count(*) from public.search_profiles where id = '00000000-0000-0000-0000-000000000301'), 1::bigint, 'user A sees own search profile');
select is((select count(*) from public.job_search_runs where id = '00000000-0000-0000-0000-000000000401'), 1::bigint, 'user A sees own search run');
select is((select count(*) from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000401'), 1::bigint, 'user A sees own source');
select is((select count(*) from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000401'), 1::bigint, 'user A sees own run-job link');
select is((select count(*) from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000401'), 1::bigint, 'user A sees own provenance');
select is(
    (select case when not exists (select 1 from public.search_profiles where id = '00000000-0000-0000-0000-000000000302')
                      and not exists (select 1 from public.job_search_runs where id = '00000000-0000-0000-0000-000000000403')
                      and not exists (select 1 from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000403')
                      and not exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000403')
                      and not exists (select 1 from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000403')
                 then true else false end),
    true,
    'user A cannot see user B discovery rows'
);

update public.search_profiles set target_roles = ARRAY['hijacked'] where id = '00000000-0000-0000-0000-000000000302';
update public.job_search_runs set status = 'failed' where id = '00000000-0000-0000-0000-000000000403';
delete from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000403';
select throws_ok(
    $$ insert into public.job_search_run_jobs (search_run_id, job_id)
       values ('00000000-0000-0000-0000-000000000403', '00000000-0000-0000-0000-000000000501') $$,
    '42501',
    'new row violates row-level security policy for table "job_search_run_jobs"',
    'RLS rejects user A cross-user run-job inserts'
);
update public.job_provenance
set canonical_url = 'https://example.test/blocked'
where search_run_id = '00000000-0000-0000-0000-000000000403';

select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000002"}', true);
select is((select count(*) from public.search_profiles where id = '00000000-0000-0000-0000-000000000302'), 1::bigint, 'user B sees own search profile');
select is((select count(*) from public.job_search_runs where id = '00000000-0000-0000-0000-000000000403'), 1::bigint, 'user B sees own search run');
select is((select count(*) from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000403'), 1::bigint, 'user B sees own source');
select is((select count(*) from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000403'), 1::bigint, 'user B sees own run-job link');
select is((select count(*) from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000403'), 1::bigint, 'user B sees own provenance');
select is(
    (select case when not exists (select 1 from public.search_profiles where id = '00000000-0000-0000-0000-000000000301')
                      and not exists (select 1 from public.job_search_runs where id = '00000000-0000-0000-0000-000000000401')
                      and not exists (select 1 from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000401')
                      and not exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000401')
                      and not exists (select 1 from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000401')
                 then true else false end),
    true,
    'user B cannot see user A discovery rows'
);
update public.search_profiles set target_roles = ARRAY['hijacked'] where id = '00000000-0000-0000-0000-000000000301';
update public.job_search_runs set status = 'failed' where id = '00000000-0000-0000-0000-000000000401';
delete from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000401';
select throws_ok(
    $$ insert into public.job_search_run_jobs (search_run_id, job_id)
       values ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000502') $$,
    '42501',
    'new row violates row-level security policy for table "job_search_run_jobs"',
    'RLS rejects user B cross-user run-job inserts'
);
update public.job_provenance
set canonical_url = 'https://example.test/blocked'
where search_run_id = '00000000-0000-0000-0000-000000000401';
reset role;
select set_config('request.jwt.claims', '', true);

select is(
    (select case when (select target_roles from public.search_profiles where id = '00000000-0000-0000-0000-000000000301') = ARRAY['Data Engineer']::text[]
                      and (select target_roles from public.search_profiles where id = '00000000-0000-0000-0000-000000000302') = ARRAY['Platform Engineer']::text[]
                 then true else false end),
    true,
    'RLS blocks cross-user search profile updates with temporary DML grants'
);
select is(
    (select case when (select status from public.job_search_runs where id = '00000000-0000-0000-0000-000000000401') = 'queued'
                      and (select status from public.job_search_runs where id = '00000000-0000-0000-0000-000000000403') = 'queued'
                 then true else false end),
    true,
    'RLS blocks cross-user search run updates with temporary DML grants'
);
select is(
    (select case when (select count(*) from public.job_sources where search_run_id in ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000403')) = 2
                 then true else false end),
    true,
    'RLS blocks cross-user source deletes with temporary DML grants'
);
select is(
    (select case when exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000401' and job_id = '00000000-0000-0000-0000-000000000501')
                      and exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000403' and job_id = '00000000-0000-0000-0000-000000000502')
                      and not exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000403' and job_id = '00000000-0000-0000-0000-000000000501')
                      and not exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000401' and job_id = '00000000-0000-0000-0000-000000000502')
                 then true else false end),
    true,
    'RLS blocks cross-user run-job inserts with temporary DML grants'
);
select is(
    (select case when (select canonical_url from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000401') = 'https://example.test/jobs/1'
                      and (select canonical_url from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000403') = 'https://example.test/jobs/2'
                 then true else false end),
    true,
    'RLS blocks cross-user provenance updates with temporary DML grants'
);

select throws_ok(
    $$ delete from public.jobs where id = '00000000-0000-0000-0000-000000000502' $$,
    '23503',
    null,
    'rejects hard delete of a referenced shared job'
);
select lives_ok(
    $$ delete from public.job_search_runs where id = '00000000-0000-0000-0000-000000000403' $$,
    'deleting a run removes its source, link, and provenance rows'
);
select is(
    (select case when not exists (select 1 from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000403')
                      and not exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000403')
                      and not exists (select 1 from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000403')
                      and exists (select 1 from public.jobs where id = '00000000-0000-0000-0000-000000000502')
                 then true else false end),
    true,
    'run deletion preserves shared jobs and removes dependent rows'
);

select lives_ok(
    $$ delete from public.candidate_profiles where id = '00000000-0000-0000-0000-000000000201' $$,
    'cascades discovery data when its candidate profile is deleted'
);
select is(
    (select case when not exists (select 1 from public.candidate_profiles where id = '00000000-0000-0000-0000-000000000201')
                      and exists (select 1 from public.candidate_profiles where id = '00000000-0000-0000-0000-000000000202')
                      and not exists (select 1 from public.search_profiles where id = '00000000-0000-0000-0000-000000000301')
                      and not exists (select 1 from public.job_search_runs where id = '00000000-0000-0000-0000-000000000401')
                      and not exists (select 1 from public.job_sources where search_run_id = '00000000-0000-0000-0000-000000000401')
                      and not exists (select 1 from public.job_search_run_jobs where search_run_id = '00000000-0000-0000-0000-000000000401')
                      and not exists (select 1 from public.job_provenance where search_run_id = '00000000-0000-0000-0000-000000000401')
                 then true else false end),
    true,
    'candidate deletion cascades search profiles, runs, sources, joins, and provenance'
);
select is(
    (select count(*) from public.jobs where id = '00000000-0000-0000-0000-000000000501'),
    1::bigint,
    'candidate deletion preserves the global job catalog row'
);

select * from finish();
rollback;
