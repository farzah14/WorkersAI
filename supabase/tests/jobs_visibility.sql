begin;
create extension if not exists pgtap;

select plan(15);

select is(
    (select count(*) from pg_tables
     where schemaname = 'public' and tablename = 'jobs'),
    1::bigint,
    'shared jobs table exists'
);

select is(
    (select coalesce(rowsecurity, false) from pg_tables
     where schemaname = 'public' and tablename = 'jobs'),
    true,
    'shared jobs rls is enabled'
);

select is(
    (select count(*) from pg_policies
     where schemaname = 'public'
       and tablename = 'jobs'
       and policyname = 'jobs_authenticated_select'
       and cmd = 'SELECT'
       and roles @> ARRAY['authenticated']::name[]
       and position('true' in lower(coalesce(qual, ''))) > 0),
    1::bigint,
    'authenticated shared jobs select policy exists'
);

select has_table_privilege(
    'authenticated', 'public.jobs', 'select',
    'authenticated role can select the shared jobs catalog'
);
select has_table_privilege(
    'service_role', 'public.jobs', 'select',
    'service role can select the shared jobs catalog'
);
select is(
    has_table_privilege('anon', 'public.jobs', 'select'),
    false,
    'anonymous role cannot select the shared jobs catalog'
);
select is(
    has_table_privilege('authenticated', 'public.jobs', 'insert'),
    false,
    'authenticated role cannot insert shared catalog rows'
);
select is(
    has_table_privilege('authenticated', 'public.jobs', 'update'),
    false,
    'authenticated role cannot update shared catalog rows'
);
select is(
    has_table_privilege('authenticated', 'public.jobs', 'delete'),
    false,
    'authenticated role cannot delete shared catalog rows'
);

set local role service_role;
insert into public.jobs (
    id, fingerprint, title, company, description, source_name,
    original_url, canonical_url
)
values (
    '00000000-0000-0000-0000-000000000591',
    'jobs-visibility-fixture',
    'Visibility Fixture',
    'Fixture Co',
    'Synthetic shared catalog row for RLS visibility tests.',
    'fixture',
    'https://example.test/jobs/visibility',
    'https://example.test/jobs/visibility'
);
reset role;

set local role authenticated;
select is(
    (select count(*) from public.jobs
     where id = '00000000-0000-0000-0000-000000000591'),
    1::bigint,
    'authenticated role sees the shared job'
);
select throws_ok(
    $$
      insert into public.jobs (
        id, fingerprint, title, company, description, source_name,
        original_url, canonical_url
      ) values (
        '00000000-0000-0000-0000-000000000592',
        'jobs-visibility-denied',
        'Denied Fixture',
        'Fixture Co',
        'Synthetic denied insert.',
        'fixture',
        'https://example.test/jobs/denied',
        'https://example.test/jobs/denied'
      )
    $$,
    '42501',
    null,
    'authenticated role cannot insert shared jobs'
);
select throws_ok(
    $$
      update public.jobs
      set title = 'Changed by authenticated user'
      where id = '00000000-0000-0000-0000-000000000591'
    $$,
    '42501',
    null,
    'authenticated role cannot update shared jobs'
);
select throws_ok(
    $$
      delete from public.jobs
      where id = '00000000-0000-0000-0000-000000000591'
    $$,
    '42501',
    null,
    'authenticated role cannot delete shared jobs'
);
reset role;

set local role anon;
select throws_ok(
    $$ select * from public.jobs
       where id = '00000000-0000-0000-0000-000000000591' $$,
    '42501',
    null,
    'anonymous role cannot read shared jobs'
);
reset role;

select is(
    (select title from public.jobs
     where id = '00000000-0000-0000-0000-000000000591'),
    'Visibility Fixture',
    'denied authenticated mutations leave the shared job unchanged'
);

select * from finish();
rollback;
