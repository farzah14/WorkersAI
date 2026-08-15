import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { saveProfileRequestSchema } from "@/lib/profile/schema";
import {
  isActiveCvConflict,
  isVersionRace,
  saveCandidateProfile,
  supabaseProfileRepo,
} from "@/lib/profile/save-profile";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const { data: activeCv } = await supabase
    .from("cvs")
    .select("id")
    .eq("user_id", user.id)
    .eq("is_active", true)
    .maybeSingle();
  if (!activeCv) return NextResponse.json({ profile: null, cv_id: null });

  const { data: profileRow, error } = await supabase
    .from("candidate_profiles")
    .select("profile, version, confirmed_at")
    .eq("cv_id", activeCv.id)
    .order("version", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) return NextResponse.json({ error: "profile fetch failed" }, { status: 500 });

  if (!profileRow) return NextResponse.json({ profile: null, cv_id: activeCv.id });

  return NextResponse.json({
    profile: profileRow.profile,
    cv_id: activeCv.id,
    version: profileRow.version,
    confirmed: profileRow.confirmed_at != null,
  });
}

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  const parsed = saveProfileRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "validation_failed", details: parsed.error.flatten() }, { status: 400 });
  }
  const { cv_id: cvId, profile } = parsed.data;

  const { data: ownedCv } = await supabase
    .from("cvs")
    .select("id")
    .eq("id", cvId)
    .eq("user_id", user.id)
    .maybeSingle();
  if (!ownedCv) return NextResponse.json({ error: "cv_not_found" }, { status: 404 });

  const result = await saveCandidateProfile(supabaseProfileRepo(supabase), {
    userId: user.id,
    cvId,
    profile,
  });
  if (!result.ok) {
    if (isActiveCvConflict(result.error)) {
      return NextResponse.json({ error: "active_cv_conflict" }, { status: 409 });
    }
    if (isVersionRace(result.error)) {
      return NextResponse.json({ error: "save_conflict" }, { status: 409 });
    }
    return NextResponse.json({ error: "save failed" }, { status: 500 });
  }

  return NextResponse.json({ ok: true, version: result.version }, { status: 201 });
}