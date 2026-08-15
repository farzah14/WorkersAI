"use server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { makeCvActive, supabaseProfileRepo } from "@/lib/profile/save-profile";

export async function setActiveCv(formData: FormData) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const cvId = String(formData.get("cvId") ?? "");
  if (!cvId) return;

  await makeCvActive(supabaseProfileRepo(supabase), { userId: user.id, cvId });
  revalidatePath("/cvs");
}