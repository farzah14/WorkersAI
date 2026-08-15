import { z } from "zod";

export const SENIORITIES = [
  "intern",
  "junior",
  "mid",
  "senior",
  "lead",
  "manager",
  "executive",
  "unknown",
] as const;

function stripEmptyStrings(value: unknown): unknown {
  if (!Array.isArray(value)) return value;
  return value
    .map((item) => (typeof item === "string" ? item.trim() : item))
    .filter((item) => item !== "");
}

function emptyStringToUndefined(value: unknown): unknown {
  return typeof value === "string" && value.trim() === "" ? undefined : value;
}

const optionalText = z.preprocess(
  emptyStringToUndefined,
  z.string().trim().optional().nullable(),
);

const nonEmptyTextArray = z.preprocess(
  stripEmptyStrings,
  z.array(z.string()).min(1, "At least one item is required"),
);

const optionalTextArray = z.preprocess(
  stripEmptyStrings,
  z.array(z.string()).default([]),
);

const optionalYears = z.preprocess(
  emptyStringToUndefined,
  z.number().min(0).max(80).optional().nullable(),
);

export const candidateProfileSchema = z.object({
  name: optionalText,
  current_role: optionalText,
  seniority: z.enum(SENIORITIES).default("unknown"),
  target_roles: nonEmptyTextArray,
  skills: nonEmptyTextArray,
  experience_years: optionalYears,
  languages: optionalTextArray,
  education: optionalTextArray,
});

export const saveProfileRequestSchema = z.object({
  cv_id: z.string().min(1),
  profile: candidateProfileSchema,
});

export type CandidateProfile = z.infer<typeof candidateProfileSchema>;
export type SaveProfileRequest = z.infer<typeof saveProfileRequestSchema>;