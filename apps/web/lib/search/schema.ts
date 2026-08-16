import { z } from "zod";

export const REGIONS = ["indonesia", "global"] as const;
export const WORK_MODES = ["remote", "hybrid", "on-site"] as const;
export const EMPLOYMENT_TYPES = [
  "full-time",
  "part-time",
  "contract",
  "temporary",
  "internship",
  "apprenticeship",
  "volunteer",
  "freelance",
] as const;

const MAX_SEARCH_ARRAY_ITEMS = 20;
const MAX_SEARCH_TERM_LENGTH = 200;

function normalizeArray(value: unknown): unknown {
  if (!Array.isArray(value)) return value;
  if (value.length > MAX_SEARCH_ARRAY_ITEMS) {
    return value.slice(0, MAX_SEARCH_ARRAY_ITEMS + 1);
  }

  const normalized = value
    .map((item) => (typeof item === "string" ? item.trim() : item))
    .filter((item) => item !== "");

  return Array.from(new Set(normalized));
}

function emptyStringToUndefined(value: unknown): unknown {
  return typeof value === "string" && value.trim() === "" ? undefined : value;
}

const normalizedTextArray = z.preprocess(
  normalizeArray,
  z.array(z.string().min(1).max(MAX_SEARCH_TERM_LENGTH)).max(MAX_SEARCH_ARRAY_ITEMS),
);

const normalizedOptionalTextArray = z.preprocess(
  normalizeArray,
  z
    .array(z.string().min(1).max(MAX_SEARCH_TERM_LENGTH))
    .max(MAX_SEARCH_ARRAY_ITEMS)
    .default([]),
);

const optionalText = z.preprocess(
  emptyStringToUndefined,
  z.string().trim().max(32).optional().nullable(),
);

const optionalNonNegativeNumber = z.preprocess(
  (value) => {
    if (typeof value === "string") {
      const trimmed = value.trim();
      return trimmed === "" ? undefined : Number(trimmed);
    }
    return value;
  },
  z.number().finite().min(0).optional().nullable(),
);

export const searchProfileSchema = z.object({
  candidate_profile_id: z.string().uuid(),
  region: z.enum(REGIONS),
  target_roles: normalizedTextArray.pipe(z.array(z.string().min(1)).min(1)),
  locations: normalizedOptionalTextArray,
  work_modes: z.preprocess(
    normalizeArray,
    z.array(z.enum(WORK_MODES)).max(MAX_SEARCH_ARRAY_ITEMS).default([]),
  ),
  employment_types: z.preprocess(
    normalizeArray,
    z.array(z.enum(EMPLOYMENT_TYPES)).max(MAX_SEARCH_ARRAY_ITEMS).default(["full-time"]),
  ),
  min_salary: optionalNonNegativeNumber,
  salary_currency: optionalText,
  excluded_keywords: normalizedOptionalTextArray,
  daily_enabled: z.boolean().default(false),
});

export type SearchProfile = z.infer<typeof searchProfileSchema>;
