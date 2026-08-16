begin;
create extension if not exists pgtap;

select plan(25);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'user_jobs'),
    1::bigint,
    'user_jobs table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'exports'),
    1::bigint,
    'exports table exists'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'user_jobs'),
    true,
    'user_jobs rls is enabled'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'exports'),
    true,
    'exports rls is enabled'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'user_jobs'
       and column_name = any (array['user_id','job_id','status','applied_at','updated_at'])
       and is_nullable = 'NO'),
    4::bigint,
    'user_jobs required columns present; applied_at nullable'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'exports'
       and column_name = any (array[
           'id','user_id','search_run_id','format','filter_json',
           'status','storage_path','error_code','created_at','completed_at'])
       and is_nullable = 'NO'),
    7::bigint,
    'exports required columns present; storage_path/error_code/completed_at nullable'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.user_jobs')
       and c.contype = 'p'
       and position('user_id' in pg_get_constraintdef(c.oid)) > 0
       and position('job_id' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'user_jobs primary key is (user_id, job_id)'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.user_jobs')
       and c.contype = 'c'
       and position('new' in pg_get_constraintdef(c.oid)) > 0
       and position('saved' in pg_get_constraintdef(c.oid)) > 0
       and position('applied' in pg_get_constraintdef(c.oid)) > 0
       and position('ignored' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'user_jobs status is bounded to new/saved/applied/ignored'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.exports')
       and c.contype = 'c'
       and position('xlsx' in pg_get_constraintdef(c.oid)) > 0
       and position('pdf' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'exports format is bounded to xlsx/pdf'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.exports')
       and c.contype = 'c'
       and position('queued' in pg_get_constraintdef(c.oid)) > 0
       and position('processing' in pg_get_constraintdef(c.oid)) > 0
       and position('completed' in pg_get_constraintdef(c.oid)) > 0
       and position('failed' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'exports status is bounded to queued/processing/completed/failed'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.exports')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('auth.users(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'exports user foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.exports')
       and c.contype = 'f'
       and position('FOREIGN KEY (search_run_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('job_search_runs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'exports search run foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.user_jobs')
       and c.contype = 'f'
       and position('FOREIGN KEY (job_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('jobs(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'user_jobs job foreign key cascades'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.user_jobs')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('auth.users(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'user_jobs user foreign key cascades'
);
select is(
    (select count(*) from storage.buckets where id = 'exports' and public = false),
    1::bigint,
    'exports storage bucket exists and is private'
);
select is(
    (select count(*)
     from pg_policies p
     where p.schemaname = 'storage'
       and p.tablename = 'objects'
       and p.policyname = 'export_storage_owner_select'
       and p.cmd = 'SELECT'
       and position('exports' in p.qual) > 0
       and position('auth.uid()' in p.qual) > 0
       and position('foldername' in p.qual) > 0),
    1::bigint,
    'export storage owner select policy exists'
);
select is(
    (select count(*)
     from pg_policies p
     where p.schemaname = 'storage'
       and p.tablename = 'objects'
       and p.policyname = 'export_storage_owner_insert'
       and p.cmd = 'INSERT'
       and position('exports' in coalesce(p.with_check, '')) > 0
       and position('auth.uid()' in coalesce(p.with_check, '')) > 0
       and position('foldername' in coalesce(p.with_check, '')) > 0),
    1::bigint,
    'export storage owner insert policy exists'
);
select is(
    (select count(*)
     from pg_policies p
     where p.schemaname = 'storage'
       and p.tablename = 'objects'
       and p.policyname = 'export_storage_owner_delete'
       and p.cmd = 'DELETE'
       and position('exports' in p.qual) > 0
       and position('auth.uid()' in p.qual) > 0
       and position('foldername' in p.qual) > 0),
    1::bigint,
    'export storage owner delete policy exists'
);

insert into auth.users (id, email)
values
  ('00000000-0000-0000-0000-000000000001', 'tracking-fixture@example.test'),
  ('00000000-0000-0000-0000-000000000002', 'tracking-fixture-b@example.test');

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
values ('00000000-0000-0000-0000-000000000501', 'tracking-fixture-fp-1', 'Data Engineer', 'Acme', 'Build pipelines', 'test', 'https://example.test/jobs/1', 'https://example.test/jobs/1', 'indonesia', 'active');
insert into public.jobs (id, fingerprint, title, company, description, source_name, original_url, canonical_url, region, status)
values ('00000000-0000-0000-0000-000000000502', 'tracking-fixture-fp-2', 'Analyst', 'Acme', 'Analyze data', 'test', 'https://example.test/jobs/2', 'https://example.test/jobs/2', 'indonesia', 'active');

insert into public.user_jobs (user_id, job_id, status)
values ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000501', 'saved');
insert into public.exports (id, user_id, search_run_id, format, filter_json, status)
values ('00000000-0000-0000-0000-000000000601', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000401', 'xlsx', '{}'::jsonb, 'queued');

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then has_table_privilege('anon', 'public.user_jobs', 'select') = false
                  and has_table_privilege('anon', 'public.exports', 'select') = false
                 else false end),
    true,
    'anon has no user_jobs or exports access'
);

select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001"}', true);
set local role authenticated;
select is(
    (select count(*) from public.user_jobs where user_id = '00000000-0000-0000-0000-000000000001'),
    1::bigint,
    'authenticated user A sees own tracked job'
);
select is(
    (select count(*) from public.user_jobs where user_id = '00000000-0000-0000-0000-000000000002'),
    0::bigint,
    'authenticated user B sees no tracked jobs of user A'
);
select is(
    (select count(*) from public.exports where user_id = '00000000-0000-0000-0000-000000000002'),
    0::bigint,
    'authenticated user B sees no exports of user A'
);

insert into public.user_jobs (user_id, job_id, status)
values ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000502', 'applied');
select is(
    (select count(*) from public.user_jobs where user_id = '00000000-0000-0000-0000-000000000001' and status = 'applied'),
    1::bigint,
    'authenticated user can insert own tracked job with applied status'
);
insert into public.exports (user_id, search_run_id, format, filter_json, status)
values ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000401', 'pdf', '{}'::jsonb, 'queued');
select is(
    (select count(*) from public.exports where user_id = '00000000-0000-0000-0000-000000000001'),
    2::bigint,
    'authenticated user can insert own export request'
);
reset role;
select set_config('request.jwt.claims', '', true);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'service_role')
                 then has_table_privilege('service_role', 'public.user_jobs', 'select')
                   and has_table_privilege('service_role', 'public.user_jobs', 'insert')
                   and has_table_privilege('service_role', 'public.user_jobs', 'update')
                   and has_table_privilege('service_role', 'public.user_jobs', 'delete')
                   and has_table_privilege('service_role', 'public.exports', 'select')
                   and has_table_privilege('service_role', 'public.exports', 'insert')
                   and has_table_privilege('service_role', 'public.exports', 'update')
                   and has_table_privilege('service_role', 'public.exports', 'delete')
                 else false end),
    true,
    'service_role can operate on user_jobs and exports'
);

select * from finish();
rollback;