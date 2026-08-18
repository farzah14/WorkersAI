begin;
create extension if not exists pgtap;

select plan(8);

select is(
    (select count(*)
     from pg_proc p
     join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname = 'delete_search_run'
       and p.pronargs = 2),
    1::bigint,
    'delete_search_run function exists with two arguments'
);

select is(
    (select count(*)
     from pg_proc p
     join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname = 'delete_search_run'
       and p.prosecdef),
    1::bigint,
    'delete_search_run is security definer'
);

select is(
    (select count(*)
     from pg_proc p
     join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname = 'delete_search_run'
       and has_function_privilege('service_role', p.oid, 'EXECUTE')),
    1::bigint,
    'service_role can execute delete_search_run'
);

select is(
    (select count(*)
     from pg_proc p
     join pg_namespace n on n.oid = p.pronamespace
     where n.nspname = 'public'
       and p.proname = 'delete_search_run'
       and has_function_privilege('authenticated', p.oid, 'EXECUTE')),
    0::bigint,
    'authenticated cannot execute delete_search_run directly'
);

insert into auth.users (id, email)
values (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'search-run-delete-fixture@example.test'
);

insert into public.cvs (id, user_id, original_name, mime_type)
values (
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'delete-fixture.pdf',
    'application/pdf'
);

insert into public.candidate_profiles
    (id, user_id, cv_id, version, profile, confirmed_at)
values (
    'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    1,
    '{}'::jsonb,
    now()
);

insert into public.search_profiles
    (id, user_id, candidate_profile_id, region, target_roles)
values (
    'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    'indonesia',
    '{"Data Engineer"}'
);

insert into public.job_search_runs
    (id, user_id, search_profile_id, candidate_profile_id, trigger, status)
values (
    'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
    'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    'manual',
    'partial'
);

insert into public.jobs
    (id, fingerprint, title, company, description, source_name, original_url, canonical_url)
values (
    'ffffffff-ffff-4fff-8fff-ffffffffffff',
    'delete-fixture',
    'Delete Fixture Job',
    'Fixture Co',
    'Python required',
    'Fixture',
    'https://example.test/delete-fixture',
    'https://example.test/delete-fixture'
);

insert into public.job_search_run_jobs (search_run_id, job_id)
values (
    'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
    'ffffffff-ffff-4fff-8fff-ffffffffffff'
);

insert into public.job_matches
    (user_id, search_run_id, candidate_profile_id, job_id,
     overall_score, skills_score, experience_score, education_score,
     location_score, seniority_score, language_score,
     strengths, gaps, critical_gaps, verdict, explanation, recommendations)
values (
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
    'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
    'ffffffff-ffff-4fff-8fff-ffffffffffff',
    50, 50, 50, 50, 50, 50, 50,
    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
    'potential', 'fixture', '[]'::jsonb
);

insert into public.work_items (kind, dedupe_key, payload)
values
    ('discover_jobs', 'delete-fixture-discovery', jsonb_build_object('search_run_id', 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee')),
    ('extract_job_requirements', 'delete-fixture-requirements', jsonb_build_object('job_id', 'ffffffff-ffff-4fff-8fff-ffffffffffff'));

set local role service_role;
select public.delete_search_run(
    'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'::uuid,
    'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid
);
reset role;

select is(
    (select count(*) from public.job_search_runs where id = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'),
    0::bigint,
    'deleting a run removes the run'
);
select is(
    (select count(*) from public.job_matches where search_run_id = 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'),
    0::bigint,
    'deleting a run cascades its matches'
);
select is(
    (select count(*) from public.work_items where dedupe_key like 'delete-fixture-%'),
    0::bigint,
    'deleting a run removes its queued work'
);
select is(
    (select count(*) from public.jobs where id = 'ffffffff-ffff-4fff-8fff-ffffffffffff'),
    1::bigint,
    'deleting a run keeps the shared canonical job'
);

select * from finish();
rollback;
