"use server";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { makeCvActive, supabaseProfileRepo } from "@/lib/profile/save-profile";

export type SetActiveCvState = { error: string | null };

export async function setActiveCv(
  _prevState: SetActiveCvState,
  formData: FormData,
): Promise<SetActiveCvState> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const cvId = String(formData.get("cvId") ?? "");
  if (!cvId) return { error: null };

  const result = await makeCvActive(supabaseProfileRepo(supabase), { userId: user.id, cvId });
  if (!result.ok) return { error: "Could not activate this CV. Please try again." };

  revalidatePath("/cvs");
  return { error: null };
}