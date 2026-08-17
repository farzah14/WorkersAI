import { NextResponse } from "next/server";

export const DAILY_QUOTA_LIMITS = {
  upload_cv: 10,
  manual_search: 10,
  export: 20,
} as const;

export type QuotaAction = keyof typeof DAILY_QUOTA_LIMITS;

type QuotaClient = {
  rpc: (
    fn: string,
    args: { p_user_id: string; p_action: string },
  ) => PromiseLike<{ data: unknown; error: { message?: string } | null }>;
};

export function secondsUntilNextUtcDay(now = new Date()): number {
  const next = new Date(now);
  next.setUTCHours(24, 0, 0, 0);
  return Math.max(1, Math.ceil((next.getTime() - now.getTime()) / 1000));
}

export async function consumeQuota(
  client: QuotaClient,
  userId: string,
  action: QuotaAction,
): Promise<{ allowed: boolean; retryAfterSeconds: number }> {
  const { data, error } = await client.rpc("increment_api_usage", {
    p_user_id: userId,
    p_action: action,
  });
  if (error) {
    throw new Error(`quota check failed for ${action}`);
  }
  const count = typeof data === "number" ? data : 0;
  const limit = DAILY_QUOTA_LIMITS[action];
  if (count > limit) {
    return { allowed: false, retryAfterSeconds: secondsUntilNextUtcDay() };
  }
  return { allowed: true, retryAfterSeconds: 0 };
}

export function quotaExceededResponse(retryAfterSeconds: number): NextResponse {
  return NextResponse.json(
    { error: "quota_exceeded" },
    {
      status: 429,
      headers: { "Retry-After": String(retryAfterSeconds) },
    },
  );
}