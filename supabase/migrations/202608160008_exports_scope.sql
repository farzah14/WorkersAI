-- Export requests carry a server-side scope so the worker can re-run the
-- exact selection without trusting client input twice.
alter table public.exports
  add column scope text not null default 'all'
  check (scope in ('all', 'current_filters', 'best_and_strong'));