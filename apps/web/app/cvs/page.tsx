import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { CvUploadForm } from "@/components/cv-upload-form";
import { SetActiveCvForm } from "@/components/set-active-cv-form";

export default async function CvsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: cvs } = await supabase
    .from("cvs")
    .select("id, original_name, extraction_status, is_active, retain_original, created_at")
    .order("created_at", { ascending: false });

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <h1 className="text-2xl font-semibold">My CVs</h1>
      <CvUploadForm />
      <ul className="flex flex-col gap-3">
        {cvs?.map((cv) => (
          <li key={cv.id} className="flex items-center justify-between rounded border border-gray-200 p-4">
            <div>
              <p className="font-medium">{cv.original_name}</p>
              <p className="text-sm text-gray-500">
                {cv.extraction_status}
                {cv.is_active && " · active"}
                {cv.retain_original ? " · original kept" : " · original deleted"}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <SetActiveCvForm cvId={cv.id} isActive={cv.is_active} />
              <time className="text-xs text-gray-400" dateTime={cv.created_at}>
                {new Date(cv.created_at).toLocaleDateString()}
              </time>
            </div>
          </li>
        ))}
        {(!cvs || cvs.length === 0) && <li className="text-sm text-gray-500">No CVs yet.</li>}
      </ul>
    </main>
  );
}