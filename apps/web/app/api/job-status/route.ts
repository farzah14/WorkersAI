import { NextResponse } from "next/server";
import { createClient as createServerClient } from "@/lib/supabase/server";

const JOB_STATUSES = ["new", "saved", "applied", "ignored"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type JobStatusBody = {
  jobId?: unknown;
  status?: unknown;
};

export async function POST(request: Request) {
  const supabase = await createServerClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: JobStatusBody;
  try {
    body = (await request.json()) as JobStatusBody;
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  if (
    typeof body.jobId !== "string" ||
    !UUID_RE.test(body.jobId) ||
    typeof body.status !== "string" ||
    !JOB_STATUSES.includes(body.status as JobStatus)
  ) {
    return NextResponse.json({ error: "validation_failed" }, { status: 400 });
  }

  const status = body.status as JobStatus;
  const { error } = await supabase
    .from("user_jobs")
    .upsert(
      {
        user_id: user.id,
        job_id: body.jobId,
        status,
        applied_at: status === "applied" ? new Date().toISOString() : null,
      },
      { onConflict: "user_id,job_id" },
    );

  if (error) {
    return NextResponse.json({ error: "status_update_failed" }, { status: 500 });
  }

  return NextResponse.json({ job_id: body.jobId, status });
}