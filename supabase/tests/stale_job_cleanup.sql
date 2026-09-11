begin;
create extension if not exists pgtap;

select plan(9);

insert into auth.users (id, email)
values ('93000000-0000-4000-8000-000000000001', 'stale-job-cleanup@example.test');

insert into public.cvs (id, user_id, original_name, mime_type)
values (
  '93000000-0000-4000-8000-000000000002',
  '93000000-0000-4000-8000-000000000001',
  'cleanup.pdf',
  'application/pdf'
);

insert into public.candidate_profiles
  (id, user_id, cv_id, version, profile, confirmed_at)
values (
  '93000000-0000-4000-8000-000000000003',
  '93000000-0000-4000-8000-000000000001',
  '93000000-0000-4000-8000-000000000002',
  1,
  '{}'::jsonb,
  now()
);

insert into public.search_profiles
  (id, user_id, candidate_profile_id, region, target_roles, is_current)
values
  (
    '93000000-0000-4000-8000-000000000004',
    '93000000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000003',
    'indonesia',
    '{"Data Engineer"}',
    false
  ),
  (
    '93000000-0000-4000-8000-000000000005',
    '93000000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000003',
    'global',
    '{"Data Engineer"}',
    true
  );

insert into public.job_search_runs
  (id, user_id, search_profile_id, candidate_profile_id, trigger, status)
values
  (
    '93000000-0000-4000-8000-000000000011',
    '93000000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000004',
    '93000000-0000-4000-8000-000000000003',
    'manual',
    'completed'
  ),
  (
    '93000000-0000-4000-8000-000000000012',
    '93000000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000005',
    '93000000-0000-4000-8000-000000000003',
    'manual',
    'completed'
  );

insert into public.jobs
  (id, fingerprint, title, company, location, country, description,
   source_name, original_url, canonical_url, published_at)
values
  (
    '93000000-0000-4000-8000-000000000006', 'freshness-recent',
    'Recent Job', 'Acme', 'Jakarta', 'Indonesia', 'Recent job.', 'Greenhouse',
    'https://boards.greenhouse.io/acme/jobs/recent',
    'https://boards.greenhouse.io/acme/jobs/recent', now() - interval '1 day'
  ),
  (
    '93000000-0000-4000-8000-000000000007', 'freshness-boundary',
    'Boundary Job', 'Acme', 'Jakarta', 'Indonesia', 'Boundary job.', 'Greenhouse',
    'https://boards.greenhouse.io/acme/jobs/boundary',
    'https://boards.greenhouse.io/acme/jobs/boundary', now() - interval '30 days'
  ),
  (
    '93000000-0000-4000-8000-000000000008', 'freshness-old',
    'Old Job', 'Acme', 'Jakarta', 'Indonesia', 'Old job.', 'Greenhouse',
    'https://boards.greenhouse.io/acme/jobs/old',
    'https://boards.greenhouse.io/acme/jobs/old', now() - interval '31 days'
  ),
  (
    '93000000-0000-4000-8000-000000000009', 'freshness-future',
    'Future Job', 'Acme', 'Remote', null, 'Future job.', 'Lever',
    'https://jobs.lever.co/acme/future',
    'https://jobs.lever.co/acme/future', now() + interval '1 day'
  ),
  (
    '93000000-0000-4000-8000-000000000010', 'freshness-undated',
    'Undated Job', 'Acme', 'Remote', null, 'Undated job.', 'Lever',
    'https://jobs.lever.co/acme/undated',
    'https://jobs.lever.co/acme/undated', null
  );

insert into public.job_search_run_jobs (search_run_id, job_id)
select run_id, job_id
from unnest(array[
  '93000000-0000-4000-8000-000000000011'::uuid,
  '93000000-0000-4000-8000-000000000012'::uuid
]) as run_id
cross join unnest(array[
  '93000000-0000-4000-8000-000000000006'::uuid,
  '93000000-0000-4000-8000-000000000007'::uuid,
  '93000000-0000-4000-8000-000000000008'::uuid,
  '93000000-0000-4000-8000-000000000009'::uuid,
  '93000000-0000-4000-8000-000000000010'::uuid
]) as job_id;

insert into public.job_matches
  (user_id, search_run_id, candidate_profile_id, job_id,
   overall_score, skills_score, experience_score, education_score,
   location_score, seniority_score, language_score,
   strengths, gaps, critical_gaps, verdict, explanation, recommendations)
select
  '93000000-0000-4000-8000-000000000001',
  run_id,
  '93000000-0000-4000-8000-000000000003',
  job_id,
  70, 70, 70, 70, 70, 70, 70,
  '[]', '[]', '[]', 'potential', 'test match', '[]'
from unnest(array[
  '93000000-0000-4000-8000-000000000011'::uuid,
  '93000000-0000-4000-8000-000000000012'::uuid
]) as run_id
cross join unnest(array[
  '93000000-0000-4000-8000-000000000006'::uuid,
  '93000000-0000-4000-8000-000000000007'::uuid,
  '93000000-0000-4000-8000-000000000008'::uuid,
  '93000000-0000-4000-8000-000000000009'::uuid,
  '93000000-0000-4000-8000-000000000010'::uuid
]) as job_id;

insert into public.user_jobs (user_id, job_id, status)
values
  (
    '93000000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000008',
    'saved'
  ),
  (
    '93000000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000009',
    'applied'
  );

select public.cleanup_stale_job_matches();

select is((select count(*) from public.job_matches where job_id = '93000000-0000-4000-8000-000000000006'), 2::bigint, 'recent matches remain');
select is((select count(*) from public.job_matches where job_id = '93000000-0000-4000-8000-000000000007'), 2::bigint, 'exactly thirty-day-old matches remain');
select is((select count(*) from public.job_matches where job_id = '93000000-0000-4000-8000-000000000008'), 0::bigint, 'older matches are removed in both regions');
select is((select count(*) from public.job_matches where job_id = '93000000-0000-4000-8000-000000000009'), 0::bigint, 'future matches are removed in both regions');
select is((select count(*) from public.job_matches where job_id = '93000000-0000-4000-8000-000000000010'), 0::bigint, 'undated matches are removed in both regions');
select is((select count(*) from public.job_search_run_jobs where job_id in ('93000000-0000-4000-8000-000000000008', '93000000-0000-4000-8000-000000000009', '93000000-0000-4000-8000-000000000010')), 0::bigint, 'invalid jobs are unlinked from all runs');
select is((select count(*) from public.jobs where id::text like '93000000-0000-4000-8000-0000000000%'), 5::bigint, 'shared jobs are preserved');
select is((select count(*) from public.user_jobs where user_id = '93000000-0000-4000-8000-000000000001'), 2::bigint, 'saved and applied tracking are preserved');
select is(has_function_privilege('authenticated', 'public.cleanup_stale_job_matches()', 'execute'), false, 'authenticated users cannot run stale cleanup');

select * from finish();
rollback;
