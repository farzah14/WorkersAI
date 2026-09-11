begin;
create extension if not exists pgtap;

select plan(5);

insert into auth.users (id, email)
values ('92000000-0000-4000-8000-000000000001', 'indonesia-content-cleanup@example.test');

insert into public.cvs (id, user_id, original_name, mime_type)
values (
  '92000000-0000-4000-8000-000000000002',
  '92000000-0000-4000-8000-000000000001',
  'cleanup.pdf',
  'application/pdf'
);

insert into public.candidate_profiles
  (id, user_id, cv_id, version, profile, confirmed_at)
values (
  '92000000-0000-4000-8000-000000000003',
  '92000000-0000-4000-8000-000000000001',
  '92000000-0000-4000-8000-000000000002',
  1,
  '{}'::jsonb,
  now()
);

insert into public.search_profiles
  (id, user_id, candidate_profile_id, region, target_roles)
values (
  '92000000-0000-4000-8000-000000000004',
  '92000000-0000-4000-8000-000000000001',
  '92000000-0000-4000-8000-000000000003',
  'indonesia',
  '{"Information Technology Specialist"}'
);

insert into public.job_search_runs
  (id, user_id, search_profile_id, candidate_profile_id, trigger, status)
values (
  '92000000-0000-4000-8000-000000000005',
  '92000000-0000-4000-8000-000000000001',
  '92000000-0000-4000-8000-000000000004',
  '92000000-0000-4000-8000-000000000003',
  'manual',
  'completed'
);

insert into public.jobs
  (id, fingerprint, title, company, location, country, description,
   source_name, original_url, canonical_url)
values (
  '92000000-0000-4000-8000-000000000006',
  'indonesia-content-cleanup-salary',
  'Information Technology Specialist Salary in ID',
  'Jobstreet',
  null,
  null,
  'Location: Jakarta, Indonesia. Salary guide and career advice.',
  'Tavily',
  'https://id.jobstreet.com/career-advice/role/information-technology-specialist/salary',
  'https://id.jobstreet.com/career-advice/role/information-technology-specialist/salary'
);

insert into public.job_search_run_jobs (search_run_id, job_id)
values (
  '92000000-0000-4000-8000-000000000005',
  '92000000-0000-4000-8000-000000000006'
);

insert into public.job_matches
  (user_id, search_run_id, candidate_profile_id, job_id,
   overall_score, skills_score, experience_score, education_score,
   location_score, seniority_score, language_score,
   strengths, gaps, critical_gaps, verdict, explanation, recommendations)
values (
  '92000000-0000-4000-8000-000000000001',
  '92000000-0000-4000-8000-000000000005',
  '92000000-0000-4000-8000-000000000003',
  '92000000-0000-4000-8000-000000000006',
  80, 80, 80, 80, 80, 80, 80,
  '[]', '[]', '[]', 'recommended', 'invalid content page', '[]'
);

insert into public.user_jobs (user_id, job_id, status)
values (
  '92000000-0000-4000-8000-000000000001',
  '92000000-0000-4000-8000-000000000006',
  'saved'
);

select public.cleanup_non_job_indonesia_matches();

select is(
  (select count(*) from public.job_matches where job_id = '92000000-0000-4000-8000-000000000006'),
  0::bigint,
  'Indonesia salary-advice match is removed'
);
select is(
  (select count(*) from public.job_search_run_jobs where job_id = '92000000-0000-4000-8000-000000000006'),
  0::bigint,
  'salary-advice job is unlinked from the Indonesia run'
);
select is(
  (select count(*) from public.user_jobs where job_id = '92000000-0000-4000-8000-000000000006' and status = 'saved'),
  1::bigint,
  'saved tracking state is preserved'
);
select is(
  (select count(*) from public.jobs where id = '92000000-0000-4000-8000-000000000006'),
  1::bigint,
  'shared canonical job is preserved'
);
select is(
  has_function_privilege('authenticated', 'public.cleanup_non_job_indonesia_matches()', 'execute'),
  false,
  'authenticated users cannot run the content cleanup function'
);

select * from finish();
rollback;
