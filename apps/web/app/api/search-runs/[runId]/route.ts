import { createClient as createServiceClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { z } from "zod";
import { createClient as createServerClient } from "@/lib/supabase/server";

const runIdSchema = z.string().uuid();
const terminalStatuses = new Set(["completed", "partial", "failed"]);

type StorageError = { message?: string } | null;

function isStorageNotFound(error: StorageError): boolean {
  return Boolean(error && /not found|does not exist|nosuchkey/i.test(error.message ?? ""));
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ runId: string }> },
): Promise<NextResponse> {
  const { runId } = await params;
  if (!runIdSchema.safeParse(runId).success) {
    return NextResponse.json({ error: "invalid_run_id" }, { status: 400 });
  }

  const supabase = await createServerClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();
  if (authError || !user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const serviceClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } },
  );

  const { data: run, error: runError } = await serviceClient
    .from("job_search_runs")
    .select("status")
    .eq("id", runId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (runError) {
    return NextResponse.json({ error: "search_run_lookup_failed" }, { status: 500 });
  }
  if (!run) {
    return NextResponse.json({ error: "search_run_not_found" }, { status: 404 });
  }
  if (!terminalStatuses.has(run.status)) {
    return NextResponse.json({ error: "search_run_active" }, { status: 409 });
  }

  const { data: exportRows, error: exportError } = await serviceClient
    .from("exports")
    .select("storage_path")
    .eq("user_id", user.id)
    .eq("search_run_id", runId)
    .not("storage_path", "is", null);

  if (exportError) {
    return NextResponse.json({ error: "export_lookup_failed" }, { status: 500 });
  }

  const exportPaths = (exportRows ?? [])
    .map((row) => row.storage_path)
    .filter((path): path is string => typeof path === "string" && path.length > 0);
  if (exportPaths.length > 0) {
    const { error: storageError } = await serviceClient.storage.from("exports").remove(exportPaths);
    if (storageError && !isStorageNotFound(storageError)) {
      return NextResponse.json({ error: "storage_cleanup_failed" }, { status: 500 });
    }
  }

  const { error: deleteError } = await serviceClient.rpc("delete_search_run", {
    p_run_id: runId,
    p_user_id: user.id,
  });
  if (deleteError) {
    if (deleteError.code === "P0001") {
      return NextResponse.json({ error: "search_run_active" }, { status: 409 });
    }
    if (deleteError.code === "P0002") {
      return NextResponse.json({ error: "search_run_not_found" }, { status: 404 });
    }
    return NextResponse.json({ error: "search_run_delete_failed" }, { status: 500 });
  }

  return NextResponse.json({ deleted: true });
}
