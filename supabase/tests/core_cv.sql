begin;
select plan(7);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'profiles'),
    1::bigint,
    'profiles table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'cvs'),
    1::bigint,
    'cvs table exists'
);
select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'work_items'),
    1::bigint,
    'work_items table exists'
);

select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'profiles'),
    true,
    'profiles rls is enabled'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'cvs'),
    true,
    'cvs rls is enabled'
);
select has_index('public', 'cvs', 'one_active_cv_per_user', 'partial unique index enforces one active cv');

select is(
    (select count(*) from storage.buckets where id = 'cvs' and public = false),
    1::bigint,
    'private cvs bucket exists'
);

select * from finish();
rollback;