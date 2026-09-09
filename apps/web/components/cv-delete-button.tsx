"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

type CvDeleteButtonProps = {
  cvId: string;
  cvName?: string;
  mode?: "original" | "full";
};

const labels = {
  original: "Delete original file",
  full: "Delete CV and profile",
} as const;

export function CvDeleteButton({ cvId, cvName, mode = "full" }: CvDeleteButtonProps) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      const url = new URL("/api/cvs", window.location.origin);
      url.searchParams.set("cv_id", cvId);
      url.searchParams.set("mode", mode);
      const response = await fetch(url, { method: "DELETE" });
      if (!response.ok) throw new Error("failed");
      router.refresh();
    } catch {
      setError(
        mode === "original"
          ? "Could not delete the original file. Please try again."
          : "Could not delete the CV and profile. Please try again.",
      );
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={remove}
        disabled={busy}
        aria-label={cvName ? `${labels[mode]} for ${cvName}` : labels[mode]}
        className="rounded border border-red-200 px-3 py-1 text-sm text-red-700 hover:bg-red-50 disabled:cursor-default disabled:opacity-50"
      >
        {busy ? "Deleting…" : labels[mode]}
      </button>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
