export type MatchBucket = "best" | "strong" | "potential" | "low";

export function bucketForScore(score: number): MatchBucket {
  if (score >= 90) return "best";
  if (score >= 71) return "strong";
  if (score >= 50) return "potential";
  return "low";
}