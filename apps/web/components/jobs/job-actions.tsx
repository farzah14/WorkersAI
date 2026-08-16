"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { JobStatus } from "@/app/api/job-status/route";

const buttonClass =
  "rounded-full border border-[#d9d5cc] px-4 py-2 text-sm font-semibold transition hover:border-[#d9623c] hover:text-[#d9623c] disabled:opacity-60";

export function JobActions({ jobId, status }: { jobId: string; status: JobStatus }) {
  const t = useTranslations("tracking");
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function setStatus(next: JobStatus) {
    setBusy(true);
    setError(false);
    try {
      const response = await fetch("/api/job-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, status: next }),
      });
      if (!response.ok) {
        setError(true);
        return;
      }
      router.refresh();
    } catch {
      setError(true);
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
          {status === "saved" ? t("unsave") : t("save")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setStatus("applied")}
          className={`${buttonClass} ${status === "applied" ? "bg-[#1f6b59] text-white hover:text-white" : ""}`}
        >
          {status === "applied" ? t("applied") : t("markApplied")}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setStatus("ignored")}
          className={`${buttonClass} ${status === "ignored" ? "bg-[#e8e6df] text-[#6d787e] hover:text-[#6d787e]" : ""}`}
        >
          {t("ignore")}
        </button>
      </div>
      {error && (
        <p role="alert" className="rounded-xl border border-[#e8b4a4] bg-[#fff0eb] px-4 py-2 text-sm text-[#9b351c]">
          {t("updateFailed")}
        </p>
      )}
    </div>
  );
}