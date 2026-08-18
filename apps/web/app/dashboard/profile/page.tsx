import Link from "next/link";
import { redirect } from "next/navigation";
import { CvUploadForm } from "@/components/cv-upload-form";
import { SetActiveCvForm } from "@/components/set-active-cv-form";
import { createClient } from "@/lib/supabase/server";

export default async function ProfileAndCvsPage() {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    redirect("/login");
  }

  const { data: cvs } = await supabase
    .from("cvs")
    .select("id, original_name, extraction_status, is_active, retain_original, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const activeCv = cvs?.find((c) => c.is_active);

  return (
    <main className="min-h-screen bg-[#f4f1ea] px-5 py-10 text-[#15212b] sm:px-8">
      <div className="mx-auto max-w-4xl space-y-8">
        <header className="border-b border-[#d9d5cc] pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-[#d9623c]">
            Candidate Hub
          </p>
          <h1 className="text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">
            Profile & CVs
          </h1>
          <p className="mt-2 text-[#53616a]">
            Manage your digital CV files and review your editable structured profile.
          </p>
        </header>

        {/* Active Profile Status Banner */}
        <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6 shadow-[0_12px_40px_rgba(21,33,43,0.05)] sm:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#6d787e]">
                Current Active CV
              </p>
              <h2 className="mt-1 text-xl font-bold text-[#15212b]">
                {activeCv ? activeCv.original_name : "No active CV selected"}
              </h2>
              <p className="mt-1 text-xs text-[#53616a]">
                {activeCv
                  ? `Status: ${activeCv.extraction_status} · Exactly one active CV is used for matching.`
                  : "Upload and activate a CV to start discovering jobs."}
              </p>
            </div>
            <Link
              href="/onboarding/profile"
              className="inline-flex items-center justify-center rounded-full bg-[#15212b] px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-[#263946]"
            >
              Edit Candidate Profile
            </Link>
          </div>
        </section>

        {/* Upload New CV Section */}
        <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6 shadow-[0_12px_40px_rgba(21,33,43,0.05)] sm:p-8 space-y-6">
          <h2 className="text-xl font-semibold text-[#15212b]">Upload New Digital CV</h2>
          <p className="text-sm text-[#53616a]">
            Upload a text-based PDF or DOCX file (up to 5 MB). Scanned image-only PDFs are not supported.
          </p>
          <CvUploadForm />
        </section>

        {/* Stored CVs List */}
        <section className="rounded-3xl border border-[#d9d5cc] bg-white p-6 shadow-[0_12px_40px_rgba(21,33,43,0.05)] sm:p-8 space-y-4">
          <h2 className="text-xl font-semibold text-[#15212b]">Uploaded CVs</h2>
          <ul className="divide-y divide-[#eae7df]">
            {cvs?.map((cv) => (
              <li
                key={cv.id}
                className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <p className="font-semibold text-sm text-[#15212b]">
                    {cv.original_name}
                  </p>
                  <p className="text-xs text-[#6d787e] mt-0.5">
                    Extraction:{" "}
                    <span className="capitalize">{cv.extraction_status}</span>
                    {cv.is_active && (
                      <span className="ml-2 font-semibold text-[#1f6b59]">
                        · Active
                      </span>
                    )}
                    {cv.retain_original
                      ? " · Original Kept"
                      : " · Original Deleted"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <SetActiveCvForm cvId={cv.id} isActive={cv.is_active} />
                  <time
                    className="text-xs font-mono text-[#6d787e]"
                    dateTime={cv.created_at}
                  >
                    {new Date(cv.created_at).toLocaleDateString()}
                  </time>
                </div>
              </li>
            ))}
            {(!cvs || cvs.length === 0) && (
              <li className="py-4 text-sm text-[#6d787e]">
                No CVs uploaded yet.
              </li>
            )}
          </ul>
        </section>
      </div>
    </main>
  );
}
