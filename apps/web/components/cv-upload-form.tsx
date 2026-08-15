"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

export function CvUploadForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const file = new FormData(event.currentTarget).get("file");
    if (!(file instanceof File) || file.size === 0) return;
    setUploading(true);
    setError(null);
    const body = new FormData();
    body.set("file", file);
    const response = await fetch("/api/cvs", { method: "POST", body });
    setUploading(false);
    if (!response.ok) {
      const data = (await response.json().catch(() => null)) as { error?: string } | null;
      setError(data?.error ?? "Upload failed.");
      return;
    }
    formRef.current?.reset();
    router.refresh();
  }

  return (
    <form ref={formRef} onSubmit={onSubmit} className="flex flex-col gap-3">
      <input
        name="file"
        type="file"
        accept="application/pdf,.docx"
        required
        aria-label="Choose a CV file"
        className="flex-1 rounded border border-gray-300 px-3 py-2"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={uploading}
        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {uploading ? "Uploading…" : "Upload CV"}
      </button>
    </form>
  );
}