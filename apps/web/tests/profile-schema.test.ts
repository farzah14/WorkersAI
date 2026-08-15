import { describe, expect, it } from "vitest";
import { candidateProfileSchema, SENIORITIES, type CandidateProfile } from "@/lib/profile/schema";
import {
  activeCvConflictError,
  isActiveCvConflict,
  isUniqueViolation,
  isVersionRace,
  makeCvActive,
  saveCandidateProfile,
  type ProfileRepo,
} from "@/lib/profile/save-profile";

function baseProfile(): CandidateProfile {
  return {
    seniority: "unknown",
    target_roles: ["Data Engineer"],
    skills: ["Python", "SQL"],
    languages: [],
    education: [],
  };
}

function fakeRepo(overrides: Partial<ProfileRepo> = {}): { repo: ProfileRepo; calls: string[] } {
  const calls: string[] = [];
  function wrap<A extends unknown[], R>(
    name: string,
    impl: (...args: A) => Promise<R>,
  ): (...args: A) => Promise<R> {
    return async (...args: A) => {
      calls.push(`${name}:${args.join(":")}`);
      return impl(...args);
    };
  }
  const repo: ProfileRepo = {
    nextVersion: wrap(
      "nextVersion",
      overrides.nextVersion ??
        (async () => {
          return { version: 3, error: null };
        }),
    ),
    insertProfile: wrap(
      "insertProfile",
      overrides.insertProfile ??
        (async () => {
          return { error: null };
        }),
    ),
    clearActive: wrap(
      "clearActive",
      overrides.clearActive ??
        (async () => {
          return { error: null };
        }),
    ),
    setActive: wrap(
      "setActive",
      overrides.setActive ??
        (async () => {
          return { error: null };
        }),
    ),
    currentActiveCv: wrap(
      "currentActiveCv",
      overrides.currentActiveCv ??
        (async () => {
          return { id: "cv-other" };
        }),
    ),
  };
  return { repo, calls };
}

describe("candidateProfileSchema", () => {
  it("accepts a full valid profile", () => {
    const result = candidateProfileSchema.safeParse({
      name: "Ada",
      current_role: "Data Engineer",
      seniority: "mid",
      target_roles: ["Data Engineer", "Analytics Engineer"],
      skills: ["Python", "SQL"],
      experience_years: 4,
      languages: ["English"],
      education: ["BSc Computer Science"],
    });
    expect(result.success).toBe(true);
  });

  it("fails when target_roles is empty", () => {
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), target_roles: [] }).success).toBe(false);
  });

  it("fails when target_roles contains only empty strings", () => {
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), target_roles: ["  ", ""] }).success).toBe(false);
  });

  it("fails when skills is empty", () => {
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), skills: [] }).success).toBe(false);
  });

  it("fails when skills contains only empty strings", () => {
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), skills: ["", " "] }).success).toBe(false);
  });

  it.each(SENIORITIES)("accepts supported seniority value %s", (seniority) => {
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), seniority }).success).toBe(true);
  });

  it("rejects unsupported seniority values", () => {
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), seniority: "principal" }).success).toBe(false);
  });

  it("defaults seniority to unknown and languages/education to empty arrays", () => {
    const result = candidateProfileSchema.safeParse(baseProfile());
    expect(result.success).toBe(true);
    if (!result.success) return;
    expect(result.data.seniority).toBe("unknown");
    expect(result.data.languages).toEqual([]);
    expect(result.data.education).toEqual([]);
    expect(result.data.name).toBeUndefined();
    expect(result.data.experience_years).toBeUndefined();
  });

  it("strips empty strings from arrays and optional text", () => {
    const result = candidateProfileSchema.safeParse({
      name: "  ",
      target_roles: [" Data Engineer ", " "],
      skills: ["Python"],
      languages: ["English", ""],
      education: [],
    });
    expect(result.success).toBe(true);
    if (!result.success) return;
    expect(result.data.name).toBeUndefined();
    expect(result.data.target_roles).toEqual(["Data Engineer"]);
    expect(result.data.languages).toEqual(["English"]);
  });

  it("enforces experience_years bounds of 0 to 80", () => {
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), experience_years: -1 }).success).toBe(false);
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), experience_years: 81 }).success).toBe(false);
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), experience_years: 0 }).success).toBe(true);
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), experience_years: 80 }).success).toBe(true);
    expect(candidateProfileSchema.safeParse({ ...baseProfile(), experience_years: null }).success).toBe(true);
  });
});

describe("error mapping", () => {
  it("detects PostgreSQL unique violations", () => {
    expect(isUniqueViolation({ code: "23505", message: "duplicate key" })).toBe(true);
    expect(isUniqueViolation({ code: "42P01", message: "no table" })).toBe(false);
    expect(isUniqueViolation(null)).toBe(false);
  });

  it("produces and detects the active_cv_conflict sentinel", () => {
    const error = activeCvConflictError();
    expect(isActiveCvConflict(error)).toBe(true);
    expect(isActiveCvConflict({ code: "23505", message: "duplicate key" })).toBe(false);
  });
});

describe("makeCvActive", () => {
  it("clears other active CVs then sets the selected one", async () => {
    const { repo, calls } = fakeRepo();
    const result = await makeCvActive(repo, { userId: "u1", cvId: "cv-1" });
    expect(result.ok).toBe(true);
    expect(calls).toContain("clearActive:u1:cv-1");
    expect(calls).toContain("setActive:u1:cv-1");
    expect(calls.filter((c) => c.startsWith("setActive:")).length).toBe(1);
  });

  it("treats a conflict as success when the target is already active", async () => {
    const { repo, calls } = fakeRepo({
      async setActive() {
        return { error: { code: "23505", message: "duplicate key" } };
      },
      async currentActiveCv() {
        return { id: "cv-1" };
      },
    });
    const result = await makeCvActive(repo, { userId: "u1", cvId: "cv-1" });
    expect(result.ok).toBe(true);
    expect(calls.filter((c) => c.startsWith("setActive:")).length).toBe(1);
  });

  it("retries once after re-reading the active CV, then succeeds", async () => {
    let attempts = 0;
    const { repo, calls } = fakeRepo({
      async setActive() {
        attempts += 1;
        if (attempts === 1) return { error: { code: "23505", message: "duplicate key" } };
        return { error: null };
      },
    });
    const result = await makeCvActive(repo, { userId: "u1", cvId: "cv-1" });
    expect(result.ok).toBe(true);
    expect(calls.filter((c) => c.startsWith("currentActiveCv:")).length).toBe(1);
    expect(calls.filter((c) => c.startsWith("setActive:")).length).toBe(2);
  });

  it("returns active_cv_conflict when the retry also hits the unique index", async () => {
    const { repo } = fakeRepo({
      async setActive() {
        return { error: { code: "23505", message: "duplicate key" } };
      },
      async currentActiveCv() {
        return { id: "cv-other" };
      },
    });
    const result = await makeCvActive(repo, { userId: "u1", cvId: "cv-1" });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(isActiveCvConflict(result.error)).toBe(true);
  });

  it("propagates non-conflict errors without retrying", async () => {
    const { repo, calls } = fakeRepo({
      async setActive() {
        return { error: { code: "42P01", message: "no table" } };
      },
    });
    const result = await makeCvActive(repo, { userId: "u1", cvId: "cv-1" });
    expect(result.ok).toBe(false);
    expect(calls.filter((c) => c.startsWith("setActive:")).length).toBe(1);
  });
});

describe("saveCandidateProfile", () => {
  it("inserts the next version, confirms it, and activates the CV", async () => {
    const { repo, calls } = fakeRepo();
    const result = await saveCandidateProfile(repo, {
      userId: "u1",
      cvId: "cv-1",
      profile: { ...baseProfile(), seniority: "mid" },
    });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.version).toBe(3);
    expect(calls.some((c) => c.startsWith("insertProfile:u1:cv-1:3:"))).toBe(true);
  });

  it("propagates non-conflict insert failures without retrying and skips activation", async () => {
    const { repo, calls } = fakeRepo({
      async insertProfile() {
        return { error: { code: "42P01", message: "no table" } };
      },
    });
    const result = await saveCandidateProfile(repo, {
      userId: "u1",
      cvId: "cv-1",
      profile: baseProfile(),
    });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.code).toBe("42P01");
    expect(calls.filter((c) => c.startsWith("insertProfile:")).length).toBe(1);
    expect(calls.filter((c) => c.startsWith("nextVersion:")).length).toBe(1);
    expect(calls.some((c) => c.startsWith("setActive:"))).toBe(false);
  });

  it("retries the version race once after re-reading max(version) and succeeds", async () => {
    let nextVersionCalls = 0;
    let insertCalls = 0;
    const { repo, calls } = fakeRepo({
      async nextVersion() {
        nextVersionCalls += 1;
        return { version: nextVersionCalls === 1 ? 3 : 4, error: null };
      },
      async insertProfile() {
        insertCalls += 1;
        if (insertCalls === 1) return { error: { code: "23505", message: "duplicate key value" } };
        return { error: null };
      },
    });
    const result = await saveCandidateProfile(repo, {
      userId: "u1",
      cvId: "cv-1",
      profile: { ...baseProfile(), seniority: "mid" },
    });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.version).toBe(4);
    expect(nextVersionCalls).toBe(2);
    expect(insertCalls).toBe(2);
    expect(calls.some((c) => c.startsWith("insertProfile:u1:cv-1:4:"))).toBe(true);
    expect(calls.some((c) => c.startsWith("setActive:"))).toBe(true);
  });

  it("returns a user-safe version-race error after two 23505 insert failures without activating", async () => {
    const { repo, calls } = fakeRepo({
      async nextVersion() {
        return { version: 3, error: null };
      },
      async insertProfile() {
        return { error: { code: "23505", message: "duplicate key value" } };
      },
    });
    const result = await saveCandidateProfile(repo, {
      userId: "u1",
      cvId: "cv-1",
      profile: baseProfile(),
    });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(isVersionRace(result.error)).toBe(true);
    expect(isActiveCvConflict(result.error)).toBe(false);
    expect(calls.filter((c) => c.startsWith("insertProfile:")).length).toBe(2);
    expect(calls.filter((c) => c.startsWith("nextVersion:")).length).toBe(2);
    expect(calls.some((c) => c.startsWith("setActive:"))).toBe(false);
    expect(calls.some((c) => c.startsWith("clearActive:"))).toBe(false);
  });

  it("returns active_cv_conflict when activation ultimately fails", async () => {
    const { repo } = fakeRepo({
      async setActive() {
        return { error: { code: "23505", message: "duplicate key" } };
      },
      async currentActiveCv() {
        return { id: "cv-other" };
      },
    });
    const result = await saveCandidateProfile(repo, {
      userId: "u1",
      cvId: "cv-1",
      profile: baseProfile(),
    });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(isActiveCvConflict(result.error)).toBe(true);
  });
});