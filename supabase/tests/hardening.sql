begin;
create extension if not exists pgtap;

select plan(20);

select is(
    (select count(*) from pg_tables where schemaname = 'public' and tablename = 'api_usage_windows'),
    1::bigint,
    'api_usage_windows table exists'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.api_usage_windows')
       and c.contype = 'p'
       and position('user_id' in pg_get_constraintdef(c.oid)) > 0
       and position('action' in pg_get_constraintdef(c.oid)) > 0
       and position('window_start' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'api_usage_windows primary key is (user_id, action, window_start)'
);
select is(
    (select count(*)
     from pg_constraint c
     where c.conrelid = to_regclass('public.api_usage_windows')
       and c.contype = 'f'
       and position('FOREIGN KEY (user_id)' in pg_get_constraintdef(c.oid)) > 0
       and position('auth.users(id)' in pg_get_constraintdef(c.oid)) > 0
       and position('ON DELETE CASCADE' in pg_get_constraintdef(c.oid)) > 0),
    1::bigint,
    'api_usage_windows user foreign key cascades'
);
select is(
    (select rowsecurity from pg_tables where schemaname = 'public' and tablename = 'api_usage_windows'),
    true,
    'api_usage_windows rls is enabled'
);
select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'api_usage_windows'
       and column_name = 'count'
       and column_default = '0'),
    1::bigint,
    'api_usage_windows count defaults to zero'
);

select is(
    (select count(*)
     from information_schema.columns
     where table_schema = 'public' and table_name = 'job_search_runs'
       and column_name = 'idempotency_key'
       and is_nullable = 'YES'),
    1::bigint,
    'job_search_runs idempotency_key column exists and is nullable'
);
select is(
    (select count(*)
     from pg_indexes
     where schemaname = 'public'
       and tablename = 'job_search_runs'
       and indexname = 'job_search_runs_idempotency_key_unique'
       and indexdef like '%WHERE (idempotency_key IS NOT NULL)%'),
    1::bigint,
    'job_search_runs idempotency key has a partial unique index'
);

select is(
    (select count(*)
     from pg_indexes
     where schemaname = 'public'
       and tablename = 'work_items'
       and indexname = 'work_items_ready_idx'
       and indexdef like '%status%'
       and indexdef like '%available_at%'
       and indexdef like '%created_at%'
       and indexdef like '%WHERE (status = ''queued''::text)%'),
    1::bigint,
    'work_items ready queue partial index exists'
);

select is(
    (select count(*) from pg_proc where proname = 'increment_api_usage'),
    1::bigint,
    'increment_api_usage function exists'
);
select is(
    (select count(*) from pg_proc p where p.proname = 'increment_api_usage' and p.prosecdef),
    1::bigint,
    'increment_api_usage is security definer'
);

insert into auth.users (id, email)
values ('00000000-0000-0000-0000-000000000001', 'hardening-fixture@example.test');

set local role service_role;
select is(
    public.increment_api_usage('00000000-0000-0000-0000-000000000001'::uuid, 'upload_cv'), 1,
    'first quota increment returns one'
);
select is(
    public.increment_api_usage('00000000-0000-0000-0000-000000000001'::uuid, 'upload_cv'), 2,
    'second quota increment in same window returns two'
);
select is(
    (select count(*) from public.api_usage_windows
     where user_id = '00000000-0000-0000-0000-000000000001'),
    1::bigint,
    'quota increments collapse into one window row'
);
select is(
    (select date_trunc('day', window_start) = date_trunc('day', now())
     from public.api_usage_windows
     where user_id = '00000000-0000-0000-0000-000000000001'),
    true,
    'quota window is bucketed to the UTC day'
);
select is(
    (select count(*) from public.api_usage_windows
     where action = 'export'
       and user_id = '00000000-0000-0000-0000-000000000001'),
    0::bigint,
    'different action uses a separate window'
);
select is(
    (select count(*) from pg_proc p
     where p.proname = 'increment_api_usage'
       and has_function_privilege('authenticated', p.oid, 'EXECUTE')),
    1::bigint,
    'authenticated role can execute quota function'
);
select is(
    (select count(*) from pg_proc p
     where p.proname = 'increment_api_usage'
       and has_function_privilege('anon', p.oid, 'EXECUTE')),
    0::bigint,
    'anon cannot execute quota function'
);

select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-000000000001"}', true);
set local role authenticated;
select is(
    public.increment_api_usage('00000000-0000-0000-0000-000000000001'::uuid, 'manual_search'), 1,
    'authenticated user can increment quota through rpc'
);
reset role;
select set_config('request.jwt.claims', '', true);

select is(
    (select case when exists (select 1 from pg_roles where rolname = 'anon')
                 then has_table_privilege('anon', 'public.api_usage_windows', 'select') = false
                   and has_table_privilege('anon', 'public.api_usage_windows', 'insert') = false
                 else false end),
    true,
    'anon has no direct api_usage_windows access'
);
select is(
    (select count(*) from pg_policies where schemaname = 'public' and tablename = 'api_usage_windows'),
    0::bigint,
    'api_usage_windows has no direct client policies; rpc is the only path'
);

select * from finish();
rollback;