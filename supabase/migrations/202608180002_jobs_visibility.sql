-- Canonical job records are shared catalog data, not owner-scoped records.
-- Keep authenticated read access available for nested match/job queries.

alter table public.jobs disable row level security;
