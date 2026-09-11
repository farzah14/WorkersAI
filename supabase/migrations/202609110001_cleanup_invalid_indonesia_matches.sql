-- Remove clearly invalid historical Indonesia search results while preserving
-- shared catalog rows and user_jobs tracking state.

create or replace function public.cleanup_invalid_indonesia_matches()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  removed_matches integer := 0;
begin
  delete from public.job_matches as match
  using public.job_search_runs as run,
        public.search_profiles as profile,
        public.jobs as job
  where match.search_run_id = run.id
    and run.search_profile_id = profile.id
    and match.job_id = job.id
    and profile.region = 'indonesia'
    and not (
      (
        lower(job.source_name) in ('greenhouse', 'lever')
        or lower(job.canonical_url) ~
          '^https://([^/]+\.)?(jobstreet\.co\.id|jobstreet\.com|glints\.com|kalibrr\.com|dealls\.com|kitalulus\.com|greenhouse\.io|lever\.co|workable\.com|ashbyhq\.com|smartrecruiters\.com)/'
      )
      and (
        lower(btrim(coalesce(job.country, ''))) in
          ('id', 'idn', 'indonesia', 'republic of indonesia')
        or (
          btrim(coalesce(job.country, '')) = ''
          and (
            lower(coalesce(job.location, '')) ~
              '(^|[^a-z0-9])(indonesia|jakarta|bandung|surabaya|medan|semarang|makassar|yogyakarta|jogja|denpasar|bali|bekasi|depok|tangerang|bogor|batam|palembang|pekanbaru|pontianak|balikpapan|samarinda|banjarmasin|manado|padang|malang|solo|surakarta|aceh|sumatra|jawa|kalimantan|sulawesi|papua|maluku|nusa tenggara)([^a-z0-9]|$)'
            or lower(job.description) ~
              '(location|lokasi|based in|berlokasi di|remote within|remote in|remote from|work from|work anywhere in)[^.\n]{0,80}(indonesia|jakarta|bandung|surabaya|medan|semarang|makassar|yogyakarta|jogja|denpasar|bali|bekasi|depok|tangerang|bogor|batam|palembang|pekanbaru|pontianak|balikpapan|samarinda|banjarmasin|manado|padang|malang|solo|surakarta|aceh|sumatra|jawa|kalimantan|sulawesi|papua|maluku|nusa tenggara)'
          )
        )
      )
    );

  get diagnostics removed_matches = row_count;

  delete from public.job_search_run_jobs as run_job
  using public.job_search_runs as run,
        public.search_profiles as profile,
        public.jobs as job
  where run_job.search_run_id = run.id
    and run.search_profile_id = profile.id
    and run_job.job_id = job.id
    and profile.region = 'indonesia'
    and not (
      (
        lower(job.source_name) in ('greenhouse', 'lever')
        or lower(job.canonical_url) ~
          '^https://([^/]+\.)?(jobstreet\.co\.id|jobstreet\.com|glints\.com|kalibrr\.com|dealls\.com|kitalulus\.com|greenhouse\.io|lever\.co|workable\.com|ashbyhq\.com|smartrecruiters\.com)/'
      )
      and (
        lower(btrim(coalesce(job.country, ''))) in
          ('id', 'idn', 'indonesia', 'republic of indonesia')
        or (
          btrim(coalesce(job.country, '')) = ''
          and (
            lower(coalesce(job.location, '')) ~
              '(^|[^a-z0-9])(indonesia|jakarta|bandung|surabaya|medan|semarang|makassar|yogyakarta|jogja|denpasar|bali|bekasi|depok|tangerang|bogor|batam|palembang|pekanbaru|pontianak|balikpapan|samarinda|banjarmasin|manado|padang|malang|solo|surakarta|aceh|sumatra|jawa|kalimantan|sulawesi|papua|maluku|nusa tenggara)([^a-z0-9]|$)'
            or lower(job.description) ~
              '(location|lokasi|based in|berlokasi di|remote within|remote in|remote from|work from|work anywhere in)[^.\n]{0,80}(indonesia|jakarta|bandung|surabaya|medan|semarang|makassar|yogyakarta|jogja|denpasar|bali|bekasi|depok|tangerang|bogor|batam|palembang|pekanbaru|pontianak|balikpapan|samarinda|banjarmasin|manado|padang|malang|solo|surakarta|aceh|sumatra|jawa|kalimantan|sulawesi|papua|maluku|nusa tenggara)'
          )
        )
      )
    );

  return removed_matches;
end;
$$;

revoke all on function public.cleanup_invalid_indonesia_matches() from public, anon, authenticated;
grant execute on function public.cleanup_invalid_indonesia_matches() to service_role;

select public.cleanup_invalid_indonesia_matches();
