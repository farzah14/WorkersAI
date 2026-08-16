"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { JobStatus } from "@/app/api/job-status/route";

const buttonClass =
  "rounded-full border border-[#d9d5cc] px-4 py-2 text-sm font-semibold transition hover:border-[#d9623c] hover:text-[#d9623c] disabled:opacity-60";

export function JobActions({ jobId, status }: { jobId: string; status: JobStatus }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function setStatus(next: JobStatus) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/job-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, status: next }),
      });
      if (!response.ok) {
        setError("Could not update the job status. Try again.");
        return;
      }
      router.refresh();
    } catch {
      setError("Could not update the job status. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => setStatus(status === "saved" ? "new" : "saved")}
          className={`${buttonClass} ${status === "saved" ? "bg-[#15212b] text-white hover:text-white" : ""}`}
        >
          {status === "saved" ? "Unsave" : "Save"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setStatus("applied")}
          className={`${buttonClass} ${status === "applied" ? "bg-[#1f6b59] text-white hover:text-white" : ""}`}
        >
          {status === "applied" ? "Applied" : "Mark Applied"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setStatus("ignored")}
          className={`${buttonClass} ${status === "ignored" ? "bg-[#e8e6df] text-[#6d787e] hover:text-[#6d787e]" : ""}`}
        >
          Ignore
        </button>
      </div>
      {error && (
        <p role="alert" className="rounded-xl border border-[#e8b4a4] bg-[#fff0eb] px-4 py-2 text-sm text-[#9b351c]">
          {error}
        </p>
      )}
    </div>
  );
}