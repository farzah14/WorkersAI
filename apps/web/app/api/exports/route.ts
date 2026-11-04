import { createClient as createServiceClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { z } from "zod";
import { consumeQuota, quotaExceededResponse } from "@/lib/rate-limit";
import { createClient as createServerClient } from "@/lib/supabase/server";

const exportScopeSchema = z.enum(["all", "current_filters", "best_and_strong"]);
const exportFormatSchema = z.enum(["xlsx", "pdf"]);

const EMPLOYMENT_TYPES = [
  "full-time",
  "part-time",
  "contract",
  "temporary",
  "internship",
  "apprenticeship",
  "volunteer",
  "freelance",
] as const;

const MAX_QUERY_CODE_POINTS = 200;
const MAX_SOURCE_CODE_POINTS = 200;
const MAX_SOURCE_FILTERS = 20;

/** Normalize query text exactly like the dashboard and worker. */
function normalizeExportQuery(value: string): string {
  return value.normalize("NFC").trim().replace(/\s+/g, " ").toLowerCase();
}

function codePointLength(value: string): number {
  return Array.from(value).length;
}

const exportFiltersSchema = z
  .object({
    query: z
      .string()
      .optional()
      .transform((value) => (value === undefined ? undefined : normalizeExportQuery(value)))
      .refine(
        (value) => value === undefined || codePointLength(value) <= MAX_QUERY_CODE_POINTS,
        { message: "query_too_long" },
      ),
    region: z.array(z.enum(["indonesia", "global"])).max(2).optional(),
    work_mode: z.array(z.enum(["remote", "hybrid", "on-site"])).optional(),
    employment_type: z.array(z.enum(EMPLOYMENT_TYPES)).max(8).optional(),
    source_name: z
      .array(
        z
          .string()
          .trim()
          .min(1)
          .refine((value) => codePointLength(value) <= MAX_SOURCE_CODE_POINTS, {
            message: "source_name_too_long",
          }),
      )
      .max(MAX_SOURCE_FILTERS)
      .optional(),
    min_score: z.number().int().min(0).max(100).optional(),
    status: z.array(z.enum(["new", "saved", "applied", "ignored"])).optional(),
    exclude_ignored: z.boolean().optional(),
    date_from: z.union([z.string().date(), z.string().datetime()]).optional(),
    date_to: z.union([z.string().date(), z.string().datetime()]).optional(),
  })
  .strict()
  .refine(
    (value) => {
      if (!value.date_from || !value.date_to) return true;
      return toCalendarDate(value.date_from) <= toCalendarDate(value.date_to);
    },
    { message: "reversed_date_range" },
  );

/** Convert legacy ISO datetime inputs to UTC calendar dates. */
function toCalendarDate(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  return new Date(value).toISOString().slice(0, 10);
}

function normalizeFilterDates<T extends { date_from?: string; date_to?: string }>(filters: T): T {
  return {
    ...filters,
    ...(filters.date_from ? { date_from: toCalendarDate(filters.date_from) } : {}),
    ...(filters.date_to ? { date_to: toCalendarDate(filters.date_to) } : {}),
  };
}

const exportRequestSchema = z
  .object({
    searchRunId: z.string().uuid(),
    format: exportFormatSchema,
    scope: exportScopeSchema,
    filters: exportFiltersSchema.optional(),
  })
  .strict();

const MAX_REQUEST_BYTES = 64 * 1024;

class RequestBodyTooLarge extends Error {}

async function readJsonBody(request: Request): Promise<unknown> {
  const contentLength = request.headers.get("content-length");
  if (contentLength) {
    const parsedLength = Number(contentLength);
    if (Number.isFinite(parsedLength) && parsedLength > MAX_REQUEST_BYTES) {
      throw new RequestBodyTooLarge();
    }
  }

  if (!request.body) {
    return JSON.parse(await request.text());
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_REQUEST_BYTES) {
      await reader.cancel();
      throw new RequestBodyTooLarge();
    }
    chunks.push(value);
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return JSON.parse(new TextDecoder().decode(body));
}

export async function POST(request: Request): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await readJsonBody(request);
  } catch {
    return NextResponse.json({ error: "validation_failed" }, { status: 400 });
  }

  const parsed = exportRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "validation_failed" }, { status: 400 });
  }
  const { searchRunId, format, scope } = parsed.data;
  const filters = parsed.data.filters ? normalizeFilterDates(parsed.data.filters) : undefined;

  const supabase = await createServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { data: run } = await supabase
    .from("job_search_runs")
    .select("id")
    .eq("id", searchRunId)
    .eq("user_id", user.id)
    .maybeSingle();
  if (!run) {
    return NextResponse.json({ error: "run_not_found" }, { status: 404 });
  }

  try {
    const quota = await consumeQuota(supabase, user.id, "export");
    if (!quota.allowed) {
      return quotaExceededResponse(quota.retryAfterSeconds);
    }
  } catch {
    return NextResponse.json({ error: "quota check failed" }, { status: 500 });
  }

  const { data: exportRow, error: insertError } = await supabase
    .from("exports")
    .insert({
      user_id: user.id,
      search_run_id: searchRunId,
      format,
      scope,
      filter_json: filters ?? {},
      status: "queued",
    })
    .select("id")
    .single();
  if (insertError || !exportRow) {
    return NextResponse.json({ error: "export_create_failed" }, { status: 500 });
  }

  const serviceClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false } },
  );
  const { error: enqueueError } = await serviceClient.from("work_items").insert({
    kind: "generate_export",
    dedupe_key: `generate_export:${exportRow.id}`,
    payload: { export_id: exportRow.id, user_id: user.id },
  });
  if (enqueueError) {
    return NextResponse.json({ error: "export_enqueue_failed" }, { status: 500 });
  }

  return NextResponse.json({ id: exportRow.id }, { status: 202 });
}

export async function GET(): Promise<NextResponse> {
  const supabase = await createServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { data: rows } = await supabase
    .from("exports")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const exports = [];
  for (const row of rows ?? []) {
    let downloadUrl: string | null = null;
    if (row.status === "completed" && row.storage_path) {
      const { data } = await supabase.storage.from("exports").createSignedUrl(row.storage_path, 3600);
      downloadUrl = data?.signedUrl ?? null;
    }
    exports.push({
      id: row.id,
      format: row.format,
      scope: row.scope,
      status: row.status,
      filter_json: row.filter_json,
      error_code: row.error_code,
      created_at: row.created_at,
      completed_at: row.completed_at,
      download_url: downloadUrl,
    });
  }

  return NextResponse.json({ exports });
}