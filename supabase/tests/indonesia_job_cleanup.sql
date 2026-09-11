begin;
create extension if not exists pgtap;

select plan(6);

insert into auth.users (id, email)
values ('91000000-0000-4000-8000-000000000001', 'indonesia-cleanup@example.test');

insert into public.cvs (id, user_id, original_name, mime_type)
values (
  '91000000-0000-4000-8000-000000000002',
  '91000000-0000-4000-8000-000000000001',
  'cleanup.pdf',
  'application/pdf'
);

insert into public.candidate_profiles
  (id, user_id, cv_id, version, profile, confirmed_at)
values (
  '91000000-0000-4000-8000-000000000003',
  '91000000-0000-4000-8000-000000000001',
  '91000000-0000-4000-8000-000000000002',
  1,
  '{}'::jsonb,
  now()
);

insert into public.search_profiles
  (id, user_id, candidate_profile_id, region, target_roles)
values (
  '91000000-0000-4000-8000-000000000004',
  '91000000-0000-4000-8000-000000000001',
  '91000000-0000-4000-8000-000000000003',
  'indonesia',
  '{"Data Engineer"}'
);

insert into public.job_search_runs
  (id, user_id, search_profile_id, candidate_profile_id, trigger, status)
values (
  '91000000-0000-4000-8000-000000000005',
  '91000000-0000-4000-8000-000000000001',
  '91000000-0000-4000-8000-000000000004',
  '91000000-0000-4000-8000-000000000003',
  'manual',
  'completed'
);

insert into public.jobs
  (id, fingerprint, title, company, location, country, description,
   source_name, original_url, canonical_url)
values
  (
    '91000000-0000-4000-8000-000000000006',
    'indonesia-cleanup-valid',
    'Data Engineer',
    'Valid Co',
    'Jakarta, Indonesia',
    'Indonesia',
    'Build data platforms in Jakarta.',
    'Tavily',
    'https://glints.com/id/jobs/valid',
    'https://glints.com/id/jobs/valid'
  ),
  (
    '91000000-0000-4000-8000-000000000007',
    'indonesia-cleanup-invalid',
    'Data Engineer',
    'Invalid Co',
    'Remote - Worldwide',
    null,
    'Work from anywhere worldwide.',
    'Tavily',
    'https://copied-jobs.blogspot.com/data-engineer',
    'https://copied-jobs.blogspot.com/data-engineer'
  );

insert into public.job_search_run_jobs (search_run_id, job_id)
values
  ('91000000-0000-4000-8000-000000000005', '91000000-0000-4000-8000-000000000006'),
  ('91000000-0000-4000-8000-000000000005', '91000000-0000-4000-8000-000000000007');

insert into public.job_matches
  (user_id, search_run_id, candidate_profile_id, job_id,
   overall_score, skills_score, experience_score, education_score,
   location_score, seniority_score, language_score,
   strengths, gaps, critical_gaps, verdict, explanation, recommendations)
values
  (
    '91000000-0000-4000-8000-000000000001',
    '91000000-0000-4000-8000-000000000005',
    '91000000-0000-4000-8000-000000000003',
    '91000000-0000-4000-8000-000000000006',
    80, 80, 80, 80, 80, 80, 80,
    '[]', '[]', '[]', 'recommended', 'valid', '[]'
  ),
  (
    '91000000-0000-4000-8000-000000000001',
    '91000000-0000-4000-8000-000000000005',
    '91000000-0000-4000-8000-000000000003',
    '91000000-0000-4000-8000-000000000007',
    70, 70, 70, 70, 70, 70, 70,
    '[]', '[]', '[]', 'potential', 'invalid', '[]'
  );

insert into public.user_jobs (user_id, job_id, status)
values (
  '91000000-0000-4000-8000-000000000001',
  '91000000-0000-4000-8000-000000000007',
  'saved'
);

select public.cleanup_invalid_indonesia_matches();

select is(
  (select count(*) from public.job_matches where job_id = '91000000-0000-4000-8000-000000000006'),
  1::bigint,
  'valid trusted Indonesia match remains visible'
);
select is(
  (select count(*) from public.job_matches where job_id = '91000000-0000-4000-8000-000000000007'),
  0::bigint,
  'invalid worldwide blog match is removed'
);
select is(
  (select count(*) from public.job_search_run_jobs where job_id = '91000000-0000-4000-8000-000000000007'),
  0::bigint,
  'invalid job is unlinked from the Indonesia run'
);
select is(
  (select count(*) from public.user_jobs where job_id = '91000000-0000-4000-8000-000000000007' and status = 'saved'),
  1::bigint,
  'saved tracking state is preserved'
);
select is(
  (select count(*) from public.jobs where id in ('91000000-0000-4000-8000-000000000006', '91000000-0000-4000-8000-000000000007')),
  2::bigint,
  'shared canonical jobs are preserved'
);
select is(
  has_function_privilege('authenticated', 'public.cleanup_invalid_indonesia_matches()', 'execute'),
  false,
  'authenticated users cannot run the cleanup function'
);

select * from finish();
rollback;
