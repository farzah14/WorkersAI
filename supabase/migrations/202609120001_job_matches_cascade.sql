alter table public.job_matches
  drop constraint job_matches_candidate_profile_id_fkey,
  add constraint job_matches_candidate_profile_id_fkey
    foreign key (candidate_profile_id)
    references public.candidate_profiles(id)
    on delete cascade;
