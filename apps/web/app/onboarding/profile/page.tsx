import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { ProfileForm } from "@/components/profile-form";
import { ProfileExtractionPending } from "@/components/profile-extraction-pending";
import type { CandidateProfile } from "@/lib/profile/schema";

export default async function OnboardingProfilePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: activeCv } = await supabase
    .from("cvs")
    .select("id, original_name, extraction_status")
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

  const { data: profileRow, error: profileError } = await supabase
    .from("candidate_profiles")
    .select("profile, version, confirmed_at")
    .eq("cv_id", activeCv.id)
    .order("version", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (profileError) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
        <h1 className="text-2xl font-semibold">Candidate profile</h1>
        <p className="text-red-600">Could not load the profile. Please refresh and try again.</p>
      </main>
    );
  }

  if (!profileRow) {
    if (activeCv.extraction_status === "failed") {
      return (
        <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
          <h1 className="text-2xl font-semibold">Candidate profile</h1>
          <p className="text-red-600">This CV could not be extracted. Upload another CV and try again.</p>
        </main>
      );
    }

    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
        <h1 className="text-2xl font-semibold">Candidate profile</h1>
        <ProfileExtractionPending cvName={activeCv.original_name} />
      </main>
    );
  }

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
      <ProfileForm key={`${activeCv.id}:${profileRow.version}`} cvId={activeCv.id} initial={initial} />
    </main>
  );
}
