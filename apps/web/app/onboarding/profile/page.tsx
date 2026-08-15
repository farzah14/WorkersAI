import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { ProfileForm } from "@/components/profile-form";
import type { CandidateProfile } from "@/lib/profile/schema";

export default async function OnboardingProfilePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: activeCv } = await supabase
    .from("cvs")
    .select("id")
    .eq("user_id", user.id)
    .eq("is_active", true)
    .maybeSingle();

  if (!activeCv) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
        <h1 className="text-2xl font-semibold">Candidate profile</h1>
        <p className="text-gray-600">Upload a CV first so we can build your profile from it.</p>
        <Link href="/cvs" className="text-blue-600 underline">
          Go to My CVs
        </Link>
      </main>
    );
  }

  const { data: profileRow } = await supabase
    .from("candidate_profiles")
    .select("profile, version, confirmed_at")
    .eq("cv_id", activeCv.id)
    .order("version", { ascending: false })
    .limit(1)
    .maybeSingle();

  const initial = profileRow ? (profileRow.profile as CandidateProfile) : null;
  const confirmed = profileRow != null && profileRow.confirmed_at != null;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">Candidate profile</h1>
      <p className="text-sm text-gray-600">
        {confirmed
          ? "Your profile is confirmed. Edit it below to save a new version."
          : "Review and edit the profile extracted from your CV, then save it."}
      </p>
      <ProfileForm cvId={activeCv.id} initial={initial} />
    </main>
  );
}