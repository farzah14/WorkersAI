import { NextResponse, type NextRequest } from "next/server";
import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";
import { validateCvFile } from "@/lib/cv/validation";
import { consumeQuota, quotaExceededResponse } from "@/lib/rate-limit";

function safeFilename(name: string): string {
  const cleaned = name.replace(/[^A-Za-z0-9._-]/g, "_").slice(0, 120);
  return cleaned || "cv";
}

export async function POST(request: NextRequest) {
  const supabase = await createServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "missing file" }, { status: 400 });

  const validation = validateCvFile({ type: file.type, size: file.size });
  if (!validation.ok) return NextResponse.json({ error: validation.error }, { status: 400 });

  try {
    const quota = await consumeQuota(supabase, user.id, "upload_cv");
    if (!quota.allowed) {
      return quotaExceededResponse(quota.retryAfterSeconds);
    }
  } catch {
    return NextResponse.json({ error: "quota check failed" }, { status: 500 });
  }

  const originalName = file.name || "cv.pdf";
  const { data: cvRow, error: insertError } = await supabase
    .from("cvs")
    .insert({
      user_id: user.id,
      original_name: originalName,
      mime_type: file.type,
      retain_original: true,
    })
    .select("id")
    .single();
  if (insertError || !cvRow) return NextResponse.json({ error: "could not create cv record" }, { status: 500 });

  const path = `${user.id}/${cvRow.id}/${safeFilename(originalName)}`;
  const { error: uploadError } = await supabase.storage.from("cvs").upload(path, file, {
    contentType: file.type,
  });
  if (uploadError) {
    await supabase.from("cvs").delete().eq("id", cvRow.id);
    return NextResponse.json({ error: "storage upload failed" }, { status: 500 });
  }

  const { error: pathError } = await supabase.from("cvs").update({ storage_path: path }).eq("id", cvRow.id);
  if (pathError) return NextResponse.json({ error: "could not finalize cv record" }, { status: 500 });

  const serviceClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false } },
  );
  const { error: queueError } = await serviceClient.from("work_items").insert({
    kind: "extract_cv",
    dedupe_key: `extract_cv:${cvRow.id}`,
    payload: { cv_id: cvRow.id, user_id: user.id },
  });
  if (queueError) {
    await supabase.from("cvs").delete().eq("id", cvRow.id);
    return NextResponse.json({ error: "could not enqueue cv extraction" }, { status: 500 });
  }

  return NextResponse.json({ id: cvRow.id }, { status: 201 });
}