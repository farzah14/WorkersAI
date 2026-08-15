import type { SupabaseClient } from "@supabase/supabase-js";
import type { CandidateProfile } from "./schema";

export type SupabaseError = { code?: string | null; message: string };

export type ProfileRepo = {
  nextVersion(
    cvId: string,
  ): Promise<{ version: number; error: null } | { version: null; error: SupabaseError }>;
  insertProfile(
    userId: string,
    cvId: string,
    version: number,
    profile: CandidateProfile,
  ): Promise<{ error: SupabaseError | null }>;
  clearActive(userId: string, excludeCvId: string): Promise<{ error: SupabaseError | null }>;
  setActive(userId: string, cvId: string): Promise<{ error: SupabaseError | null }>;
  currentActiveCv(userId: string): Promise<{ id: string } | null>;
};

export function isUniqueViolation(error: { code?: string | null; message?: string } | null | undefined): boolean {
  return error?.code === "23505";
}

export function activeCvConflictError(): SupabaseError {
  return { code: "23505", message: "active_cv_conflict" };
}

export function isActiveCvConflict(error: SupabaseError | null | undefined): boolean {
  return error?.code === "23505" && error?.message === "active_cv_conflict";
}

export function versionRaceError(): SupabaseError {
  return { code: "23505", message: "profile_version_conflict" };
}

export function isVersionRace(error: SupabaseError | null | undefined): boolean {
  return error?.code === "23505" && error?.message === "profile_version_conflict";
}

function isInsertVersionConflict(error: SupabaseError | null | undefined): boolean {
  return isUniqueViolation(error) && !isActiveCvConflict(error);
}

function toSupabaseError(error: { code?: string | null; message: string } | null): SupabaseError | null {
  if (!error) return null;
  return { code: error.code ?? null, message: error.message };
}

export function supabaseProfileRepo(supabase: SupabaseClient): ProfileRepo {
  return {
    async nextVersion(cvId) {
      const { data, error } = await supabase
        .from("candidate_profiles")
        .select("version")
        .eq("cv_id", cvId)
        .order("version", { ascending: false })
        .limit(1);
      if (error) return { version: null, error: toSupabaseError(error)! };
      const version = (data?.[0]?.version ?? 0) + 1;
      return { version, error: null };
    },

    async insertProfile(userId, cvId, version, profile) {
      const { error } = await supabase.from("candidate_profiles").insert({
        user_id: userId,
        cv_id: cvId,
        version,
        profile,
        confirmed_at: new Date().toISOString(),
      });
      return { error: toSupabaseError(error) };
    },

    async clearActive(userId, excludeCvId) {
      const { error } = await supabase
        .from("cvs")
        .update({ is_active: false })
        .eq("user_id", userId)
        .eq("is_active", true)
        .neq("id", excludeCvId);
      return { error: toSupabaseError(error) };
    },

    async setActive(userId, cvId) {
      const { data, error } = await supabase
        .from("cvs")
        .update({ is_active: true })
        .eq("id", cvId)
        .eq("user_id", userId)
        .select("id")
        .maybeSingle();
      if (error) return { error: toSupabaseError(error) };
      if (!data) return { error: { code: null, message: "cv_not_found" } };
      return { error: null };
    },

    async currentActiveCv(userId) {
      const { data, error } = await supabase
        .from("cvs")
        .select("id")
        .eq("user_id", userId)
        .eq("is_active", true)
        .maybeSingle();
      if (error || !data) return null;
      return { id: String(data.id) };
    },
  };
}

async function activateCv(repo: ProfileRepo, userId: string, cvId: string) {
  const cleared = await repo.clearActive(userId, cvId);
  if (cleared.error) return { error: cleared.error };
  return repo.setActive(userId, cvId);
}

export async function makeCvActive(
  repo: ProfileRepo,
  input: { userId: string; cvId: string },
): Promise<{ ok: true } | { ok: false; error: SupabaseError }> {
  const { userId, cvId } = input;

  const first = await activateCv(repo, userId, cvId);
  if (first.error && !isUniqueViolation(first.error)) return { ok: false, error: first.error };
  if (!first.error) return { ok: true };

  const current = await repo.currentActiveCv(userId);
  if (current && current.id === cvId) return { ok: true };

  const retry = await activateCv(repo, userId, cvId);
  if (retry.error && !isUniqueViolation(retry.error)) return { ok: false, error: retry.error };
  if (!retry.error) return { ok: true };

  return { ok: false, error: activeCvConflictError() };
}

export async function saveCandidateProfile(
  repo: ProfileRepo,
  input: { userId: string; cvId: string; profile: CandidateProfile },
): Promise<{ ok: true; version: number } | { ok: false; error: SupabaseError }> {
  const { userId, cvId, profile } = input;

  const firstVersion = await repo.nextVersion(cvId);
  if (firstVersion.error) return { ok: false, error: firstVersion.error };
  let version = firstVersion.version;

  let insertResult = await repo.insertProfile(userId, cvId, version, profile);
  if (insertResult.error && isInsertVersionConflict(insertResult.error)) {
    const reread = await repo.nextVersion(cvId);
    if (reread.error) return { ok: false, error: reread.error };
    version = reread.version;
    insertResult = await repo.insertProfile(userId, cvId, version, profile);
  }
  if (insertResult.error) {
    if (isInsertVersionConflict(insertResult.error)) return { ok: false, error: versionRaceError() };
    return { ok: false, error: insertResult.error };
  }

  const activeResult = await makeCvActive(repo, { userId, cvId });
  if (!activeResult.ok) return { ok: false, error: activeResult.error };

  return { ok: true, version };
}