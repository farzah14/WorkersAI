import { NextResponse } from "next/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";
import { createClient as createServerClient } from "@/lib/supabase/server";

const CONFIRMATION_TOKEN = "DELETE";

function isStorageNotFound(error: { message?: string } | null): boolean {
  if (!error) return false;
  return /not found|does not exist|nosuchkey/i.test(error.message ?? "");
}

export async function DELETE(request: Request): Promise<NextResponse> {
  const supabase = await createServerClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();
  if (authError || !user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_confirmation" }, { status: 400 });
  }
  const confirmation =
    typeof body === "object" && body !== null && "confirmation" in body
      ? (body as { confirmation: unknown }).confirmation
      : null;
  if (confirmation !== CONFIRMATION_TOKEN) {
    return NextResponse.json({ error: "invalid_confirmation" }, { status: 400 });
  }

  const serviceClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false } },
  );

  const { data: cvs } = await supabase
    .from("cvs")
    .select("storage_path")
    .eq("user_id", user.id)
    .not("storage_path", "is", null);
  const cvPaths = (cvs ?? []).map((row) => row.storage_path).filter((p): p is string => Boolean(p));

  const { data: exports } = await supabase
    .from("exports")
    .select("storage_path")
    .eq("user_id", user.id)
    .not("storage_path", "is", null);
  const exportPaths = (exports ?? [])
    .map((row) => row.storage_path)
    .filter((p): p is string => Boolean(p));

  if (cvPaths.length > 0) {
    const { error } = await serviceClient.storage.from("cvs").remove(cvPaths);
    if (error && !isStorageNotFound(error)) {
      return NextResponse.json({ error: "storage_cleanup_failed" }, { status: 500 });
    }
  }
  if (exportPaths.length > 0) {
    const { error } = await serviceClient.storage.from("exports").remove(exportPaths);
    if (error && !isStorageNotFound(error)) {
      return NextResponse.json({ error: "storage_cleanup_failed" }, { status: 500 });
    }
  }

  const { error: cleanupError } = await serviceClient.rpc("delete_account_cleanup", {
    p_user_id: user.id,
  });
  if (cleanupError) {
    return NextResponse.json({ error: "work_items_cleanup_failed" }, { status: 500 });
  }

  const { error: deleteError } = await serviceClient.auth.admin.deleteUser(user.id);
  if (deleteError) {
    return NextResponse.json({ error: "account_delete_failed" }, { status: 500 });
  }

  return NextResponse.json({ deleted: true }, { status: 200 });
}