begin;
create extension if not exists pgtap;

select plan(17);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'job_requirements'),
    1::bigint,
    'job_requirements table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'job_matches'),
    1::bigint,
    'job_matches table exists'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'job_matches'),
    true,
    'job_matches rls is enabled'
);

select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_requirements'
       and column_name = any (array['job_id','description_hash','requirements','extracted_at'])
       and is_nullable = 'NO'),
    4::bigint,
    'job_requirements critical columns are present and not null'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_matches'
       and column_name = any (array[
           'id','user_id','search_run_id','candidate_profile_id','job_id',
           'overall_score','skills_score','experience_score','education_score',
           'location_score','seniority_score','language_score',
           'strengths','gaps','critical_gaps','verdict','explanation',
           'recommendations','semantic_degraded','created_at'])
       and is_nullable = 'NO'),
    20::bigint,
    'job_matches critical columns are present and not null'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_matches')
       and c.contype = 'c'
       and position('CHECK' in pg_get_constraintdef(c.oid)) > 0
       and position('0' in pg_get_constraintdef(c.oid)) > 0
       and position('100' in pg_get_constraintdef(c.oid)) > 0),
    7::bigint,
    'all seven match score columns have a 0..100 check'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_matches')
       and c.contype = 'c'
       and position('verdict' in pg_get_constraintdef(c.oid)) > 0
       and position('highly_recommended' in pg_get_constraintdef(c.oid)) > 0
       and position('not_recommended' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_matches verdict is bounded to the approved set'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_matches')
       and c.contype = 'u'
       and position('search_run_id' in pg_get_constraintdef(c.oid)) > 0
       and position('job_id' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_matches is unique per search run and job'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_matches')
       and c.contype = 'f'
       and position('FOREIGN KEY (job_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('jobs(id)' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_matches job foreign key exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_matches')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('auth.users(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_matches user foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_matches')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_run_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('job_search_runs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_matches search run foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.job_matches')
       and c.contype = 'f'
       and position('FOREIGN KEY (candidate_profile_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('candidate_profiles(id)' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'job_matches candidate profile foreign key exists'
);
select is(
    (select count(*)
     from pg_policies p
     join pg_class t on t.oid = p.tablename::regclass::oid
     where t.relname = 'job_matches'
       and p.policyname = 'job_matches_owner_select'
       and p.cmd = 'SELECT'
       and position('auth.uid() = user_id' in p.qual) > 0),
    1::bigint,
    'job_matches owner select policy uses auth.uid ownership'
);

insert into auth.users (id, email)
values
  ('00000000-0000-0000-0000-000000000001', 'matching-fixture@example.test'),
  ('00000000-0000-0000-0000-000000000002', 'matching-fixture-b@example.test');

set local role service_role;
insert into public.cvs (id, user_id, original_name, mime_type)
values ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000001', 'fixture-a.pdf', 'application/pdf');
insert into public.candidate_profiles (id, user_id, cv_id, version, profile)
values ('00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000101', 1, '{}'::jsonb);
insert into public.search_profiles (id, user_id, candidate_profile_id, region, target_roles)
values ('00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000201', 'indonesia', ARRAY['Data Engineer']);
insert into public.job_search_runs (id, user_id, search_profile_id, candidate_profile_id, trigger)
values ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000301', '00000000-0000-0000-0000-000000000201', 'manual');
insert into public.jobs (id, fingerprint, title, company, description, source_name, original_url, canonical_url, region, status)
values ('00000000-0000-0000-0000-000000000501', 'matching-fixture-fp-1', 'Data Engineer', 'Acme', 'Build pipelines', 'test', 'https://example.test/jobs/1', 'https://example.test/jobs/1', 'indonesia', 'active');

insert into public.job_requirements (job_id, description_hash, requirements)
values ('00000000-0000-0000-0000-000000000501', 'abc123', '[{"category":"skill","value":"Python","criticality":"must","evidence":"Python required"}]'::jsonb);

insert into public.job_matches (
  id, user_id, search_run_id, candidate_profile_id, job_id,
  overall_score, skills_score, experience_score, education_score,
  location_score, seniority_score, language_score,
  strengths, gaps, critical_gaps, verdict, explanation, recommendations
)
values (
  '00000000-0000-0000-0000-000000000601', '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000201',
  '00000000-0000-0000-0000-000000000501',
  88, 90, 80, 100, 100, 80, 100,
  '["Python"]'::jsonb, '["AWS"]'::jsonb, '[]'::jsonb,
  'recommended', 'Strong skill fit', '["Add verified AWS projects"]'::jsonb
);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then has_table_privilege('anon', 'public.job_matches', 'select') = false
                  and has_table_privilege('anon', 'public.job_requirements', 'select') = false
                 else false end),
    true,
    'anon has no job_matches or job_requirements access'
);

select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001"}', true);
set local role authenticated;
select is(
    (select count(*) from public.job_matches where user_id = '00000000-0000-0000-0000-000000000001'),
    1::bigint,
    'authenticated user A sees own match'
);
select is(
    (select count(*) from public.job_matches where user_id = '00000000-0000-0000-0000-000000000002'),
    0::bigint,
    'authenticated user B sees no matches of user A'
);
reset role;
select set_config('request.jwt.claims', '', true);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.job_matches', 'select')
                   and has_table_privilege('service_role', 'public.job_matches', 'insert')
                   and has_table_privilege('service_role', 'public.job_matches', 'update')
                   and has_table_privilege('service_role', 'public.job_matches', 'delete')
                   and has_table_privilege('service_role', 'public.job_requirements', 'select')
                   and has_table_privilege('service_role', 'public.job_requirements', 'insert')
                   and has_table_privilege('service_role', 'public.job_requirements', 'update')
                   and has_table_privilege('service_role', 'public.job_requirements', 'delete')
                 else false end),
    true,
    'service_role can operate on job_requirements and job_matches'
);

select * from finish();
rollback;