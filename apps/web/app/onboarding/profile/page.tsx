import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { ProfileForm } from "@/components/profile-form";
import { ProfileExtractionPending } from "@/components/profile-extraction-pending";
import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import type { CandidateProfile } from "@/lib/profile/schema";

export default async function OnboardingProfilePage() {
  const t = await getTranslations("profile");
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
      <DashboardShell>
        <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
          <h1 className="text-2xl font-semibold">{t("form.heading")}</h1>
          <p className="text-gray-600">{t("uploadCvFirst")}</p>
          <Link href="/dashboard/profile" className="text-blue-600 underline">
            {t("goToMyCvs")}
          </Link>
        </main>
      </DashboardShell>
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
      <DashboardShell>
        <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
          <h1 className="text-2xl font-semibold">{t("form.heading")}</h1>
          <p className="text-red-600">{t("loadFailed")}</p>
        </main>
      </DashboardShell>
    );
  }

  if (!profileRow) {
    if (activeCv.extraction_status === "failed") {
      return (
        <DashboardShell>
          <main className="mx-auto flex max-w-3xl flex-col gap-4 p-8">
            <h1 className="text-2xl font-semibold">{t("form.heading")}</h1>
            <p className="text-red-600">{t("extractFailed")}</p>
          </main>
        </DashboardShell>
      );
    }

    return (
      <DashboardShell>
        <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
          <h1 className="text-2xl font-semibold">{t("form.heading")}</h1>
          <ProfileExtractionPending cvName={activeCv.original_name} />
        </main>
      </DashboardShell>
    );
  }

  const initial = profileRow ? (profileRow.profile as CandidateProfile) : null;
  const confirmed = profileRow != null && profileRow.confirmed_at != null;

  return (
    <DashboardShell>
      <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
        <h1 className="text-2xl font-semibold">{t("form.heading")}</h1>
        <p className="text-sm text-gray-600">
          {confirmed ? t("form.confirmedHint") : t("form.unconfirmedHint")}
        </p>
        <ProfileForm key={`${activeCv.id}:${profileRow.version}`} cvId={activeCv.id} initial={initial} />
      </main>
    </DashboardShell>
  );
}
