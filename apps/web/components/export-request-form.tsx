"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

export type ExportRequestFormProps = {
  runId: string;
  filters?: Record<string, unknown>;
};

export function ExportRequestForm({ runId, filters }: ExportRequestFormProps) {
  const router = useRouter();
  const t = useTranslations("exports");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  async function requestExport(format: "xlsx" | "pdf") {
    setBusy(true);
    setMessage(null);

    const payload: {
      searchRunId: string;
      format: "xlsx" | "pdf";
      scope: "all" | "current_filters";
      filters?: Record<string, unknown>;
    } = {
      searchRunId: runId,
      format,
      scope: filters ? "current_filters" : "all",
      filters: filters ?? undefined,
    };

    try {
      const res = await fetch("/api/exports", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error("export_request_failed");
      }

      setMessage({ type: "success", text: t("requestAccepted") });
      router.refresh();
    } catch {
      setMessage({ type: "error", text: t("requestFailed") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => requestExport("xlsx")}
          className="inline-flex items-center justify-center rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? t("creating") : t("createXlsx")}
        </button>

        <button
          type="button"
          disabled={busy}
          onClick={() => requestExport("pdf")}
          className="inline-flex items-center justify-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {busy ? t("creating") : t("createPdf")}
        </button>
      </div>

      {message && (
        <div
          role="status"
          className={`text-sm ${
            message.type === "success"
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-rose-600 dark:text-rose-400"
          }`}
        >
          {message.text}
        </div>
      )}
    </div>
  );
}
