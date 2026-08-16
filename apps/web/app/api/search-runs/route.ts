import { createClient as createServiceClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { searchProfileSchema, type SearchProfile } from "@/lib/search/schema";
import { createClient as createServerClient } from "@/lib/supabase/server";

type RpcError = {
  code?: string | null;
  message?: string | null;
};

function isMissingConfirmedActiveProfile(error: RpcError | null): boolean {
  return error?.message === "confirmed_active_profile_required";
}

function getRunId(data: unknown): string | null {
  const row = Array.isArray(data) ? data[0] : data;
  if (!row || typeof row !== "object" || !("search_run_id" in row)) return null;

  const runId = row.search_run_id;
  return typeof runId === "string" && runId.length > 0 ? runId : null;
}

function rpcArgs(userId: string, profile: SearchProfile) {
  return {
    p_user_id: userId,
    p_candidate_profile_id: profile.candidate_profile_id,
    p_region: profile.region,
    p_target_roles: profile.target_roles,
    p_locations: profile.locations,
    p_work_modes: profile.work_modes,
    p_employment_types: profile.employment_types,
    p_min_salary: profile.min_salary ?? null,
    p_salary_currency: profile.salary_currency ?? null,
    p_excluded_keywords: profile.excluded_keywords,
    p_daily_enabled: profile.daily_enabled,
  };
}

export async function POST(request: Request) {
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
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const parsed = searchProfileSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "validation_failed", details: parsed.error.flatten() },
      { status: 400 },
    );
  }

  const serviceClient = createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
        detectSessionInUrl: false,
      },
    },
  );

  const { data, error } = await serviceClient.rpc(
    "create_manual_search_run",
    rpcArgs(user.id, parsed.data),
  );

  if (error) {
    if (isMissingConfirmedActiveProfile(error)) {
      return NextResponse.json(
        { error: "confirmed_active_profile_required" },
        { status: 409 },
      );
    }
    return NextResponse.json({ error: "search_run_creation_failed" }, { status: 500 });
  }

  const runId = getRunId(data);
  if (!runId) {
    return NextResponse.json({ error: "search_run_creation_failed" }, { status: 500 });
  }

  return NextResponse.json({ run_id: runId }, { status: 202 });
}
