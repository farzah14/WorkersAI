import { describe, expect, it, vi } from "vitest";
import {
  DAILY_QUOTA_LIMITS,
  consumeQuota,
  quotaExceededResponse,
  secondsUntilNextUtcDay,
} from "@/lib/rate-limit";

function makeClient(rpcImpl: ReturnType<typeof vi.fn>) {
  return { rpc: rpcImpl };
}

describe("secondsUntilNextUtcDay", () => {
  it("returns a full day at UTC midnight", () => {
    const now = new Date("2026-08-17T00:00:00.000Z");
    expect(secondsUntilNextUtcDay(now)).toBe(86400);
  });

  it("returns one second just before midnight", () => {
    const now = new Date("2026-08-17T23:59:59.000Z");
    expect(secondsUntilNextUtcDay(now)).toBe(1);
  });

  it("never returns zero", () => {
    const now = new Date("2026-08-17T23:59:59.999Z");
    expect(secondsUntilNextUtcDay(now)).toBeGreaterThanOrEqual(1);
  });
});

describe("consumeQuota", () => {
  it("allows a request under the upload limit", async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 5, error: null });
    const result = await consumeQuota(makeClient(rpc) as never, "u-1", "upload_cv");
    expect(result.allowed).toBe(true);
    expect(result.retryAfterSeconds).toBe(0);
  });

  it("allows exactly at the limit", async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 10, error: null });
    const result = await consumeQuota(makeClient(rpc) as never, "u-1", "upload_cv");
    expect(result.allowed).toBe(true);
  });

  it("denies past the upload limit with retry-after metadata", async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 11, error: null });
    const result = await consumeQuota(makeClient(rpc) as never, "u-1", "upload_cv");
    expect(result.allowed).toBe(false);
    expect(result.retryAfterSeconds).toBeGreaterThanOrEqual(1);
  });

  it("uses the action-specific limit", async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 21, error: null });
    const result = await consumeQuota(makeClient(rpc) as never, "u-1", "export");
    expect(result.allowed).toBe(false);
  });

  it("passes user id and action to the rpc", async () => {
    const rpc = vi.fn().mockResolvedValue({ data: 1, error: null });
    await consumeQuota(makeClient(rpc) as never, "u-9", "manual_search");
    expect(rpc).toHaveBeenCalledWith("increment_api_usage", {
      p_user_id: "u-9",
      p_action: "manual_search",
    });
  });

  it("throws when the quota rpc fails", async () => {
    const rpc = vi.fn().mockResolvedValue({ data: null, error: { message: "boom" } });
    await expect(
      consumeQuota(makeClient(rpc) as never, "u-1", "upload_cv"),
    ).rejects.toThrow();
  });

  it("exports locked default limits", () => {
    expect(DAILY_QUOTA_LIMITS).toEqual({
      upload_cv: 10,
      manual_search: 10,
      export: 20,
    });
  });
});

describe("quotaExceededResponse", () => {
  it("returns 429 with retry-after header", () => {
    const response = quotaExceededResponse(1234);
    expect(response.status).toBe(429);
    expect(response.headers.get("Retry-After")).toBe("1234");
    return response.json().then((body) => {
      expect(body).toEqual({ error: "quota_exceeded" });
    });
  });
});