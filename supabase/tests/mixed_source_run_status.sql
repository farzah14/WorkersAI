begin;
create extension if not exists pgtap;

select plan(3);

insert into auth.users (id, email)
values ('94000000-0000-4000-8000-000000000001', 'mixed-source-status@example.test');

insert into public.cvs (id, user_id, original_name, mime_type)
values (
  '94000000-0000-4000-8000-000000000002',
  '94000000-0000-4000-8000-000000000001',
  'status.pdf',
  'application/pdf'
);

insert into public.candidate_profiles
  (id, user_id, cv_id, version, profile, confirmed_at)
values (
  '94000000-0000-4000-8000-000000000003',
  '94000000-0000-4000-8000-000000000001',
  '94000000-0000-4000-8000-000000000002',
  1,
  '{}'::jsonb,
  now()
);

insert into public.search_profiles
  (id, user_id, candidate_profile_id, region, target_roles)
values (
  '94000000-0000-4000-8000-000000000004',
  '94000000-0000-4000-8000-000000000001',
  '94000000-0000-4000-8000-000000000003',
  'indonesia',
  '{"Data Engineer"}'
);

insert into public.job_search_runs
  (id, user_id, search_profile_id, candidate_profile_id, trigger, status,
   normalized_count, failed_count, completed_at)
values
  (
    '94000000-0000-4000-8000-000000000005',
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000004',
    '94000000-0000-4000-8000-000000000003',
    'manual', 'failed', 0, 1, now()
  ),
  (
    '94000000-0000-4000-8000-000000000006',
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000004',
    '94000000-0000-4000-8000-000000000003',
    'manual', 'failed', 0, 2, now()
  );

insert into public.job_sources
  (search_run_id, source_type, source_key, status, result_count, error_code)
values
  ('94000000-0000-4000-8000-000000000005', 'search', 'tavily', 'success', 11, null),
  ('94000000-0000-4000-8000-000000000005', 'ats', 'greenhouse', 'failed', 0, 'config'),
  ('94000000-0000-4000-8000-000000000006', 'ats', 'greenhouse', 'failed', 0, 'config'),
  ('94000000-0000-4000-8000-000000000006', 'ats', 'lever', 'failed', 0, 'config');

select public.reclassify_mixed_source_zero_result_runs();

select is(
  (select status from public.job_search_runs where id = '94000000-0000-4000-8000-000000000005'),
  'partial',
  'mixed successful and failed sources produce a partial zero-result run'
);
select is(
  (select status from public.job_search_runs where id = '94000000-0000-4000-8000-000000000006'),
  'failed',
  'an all-failed zero-result run remains failed'
);
select is(
  has_function_privilege('authenticated', 'public.reclassify_mixed_source_zero_result_runs()', 'execute'),
  false,
  'authenticated users cannot reclassify historical runs'
);

select * from finish();
rollback;
