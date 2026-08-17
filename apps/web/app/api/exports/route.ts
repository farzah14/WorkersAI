import { createClient as createServiceClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { z } from "zod";
import { consumeQuota, quotaExceededResponse } from "@/lib/rate-limit";
import { createClient as createServerClient } from "@/lib/supabase/server";

const exportScopeSchema = z.enum(["all", "current_filters", "best_and_strong"]);
const exportFormatSchema = z.enum(["xlsx", "pdf"]);

const exportFiltersSchema = z
  .object({
    region: z.enum(["indonesia", "global"]).optional(),
    work_mode: z.array(z.enum(["remote", "hybrid", "on-site"])).optional(),
    min_score: z.number().int().min(0).max(100).optional(),
    status: z.array(z.enum(["new", "saved", "applied", "ignored"])).optional(),
    date_from: z.string().datetime().optional(),
    date_to: z.string().datetime().optional(),
  })
  .strict();

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
  const { searchRunId, format, scope, filters } = parsed.data;

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