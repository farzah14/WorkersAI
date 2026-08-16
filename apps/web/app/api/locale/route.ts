import { NextResponse } from "next/server";
import { createClient as createServerClient } from "@/lib/supabase/server";

const LOCALES = ["id", "en"] as const;
type Locale = (typeof LOCALES)[number];

export async function POST(request: Request) {
  const supabase = await createServerClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let body: { locale?: unknown };
  try {
    body = (await request.json()) as { locale?: unknown };
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  if (typeof body.locale !== "string" || !LOCALES.includes(body.locale as Locale)) {
    return NextResponse.json({ error: "validation_failed" }, { status: 400 });
  }

  const { error } = await supabase
    .from("profiles")
    .update({ locale: body.locale })
    .eq("id", user.id);

  if (error) {
    return NextResponse.json({ error: "locale_update_failed" }, { status: 500 });
  }

  return NextResponse.json({ locale: body.locale });
}