begin;
select 1 / (case when to_regclass('public.profiles') is not null then 1 else 0 end);
select 1 / (case when to_regclass('public.cvs') is not null then 1 else 0 end);
select 1 / (case when to_regclass('public.work_items') is not null then 1 else 0 end);
rollback;