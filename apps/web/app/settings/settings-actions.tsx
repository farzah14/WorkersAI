"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type CvRow = {
  id: string;
  original_name: string | null;
};

type SettingsCopy = {
  deleteOriginal: string;
  confirmationLabel: string;
  deleteAccount: string;
  accountDeleted: string;
  invalidConfirmation: string;
  error: string;
};

export function SettingsActions({
  cv,
  account,
  copy,
}: {
  cv?: CvRow;
  account?: boolean;
  copy: SettingsCopy;
}) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState("");

  async function deleteCv(cvId: string) {
    setBusy(true);
    setError(null);
    try {
      const url = new URL("/api/cvs", window.location.origin);
      url.searchParams.set("cv_id", cvId);
      const response = await fetch(url, { method: "DELETE" });
      if (!response.ok) throw new Error("failed");
      router.refresh();
    } catch {
      setError(copy.error);
      setBusy(false);
    }
  }

  async function deleteAccount() {
    if (confirmation !== "DELETE") {
      setError(copy.invalidConfirmation);
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch("/api/account/delete", {
        method: "DELETE",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ confirmation }),
      });
      if (!response.ok) throw new Error("failed");
      setMessage(copy.accountDeleted);
      router.replace("/login");
    } catch {
      setError(copy.error);
      setBusy(false);
    }
  }

  if (cv && !account) {
    return (
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => deleteCv(cv.id)}
          disabled={busy}
          className="rounded-md border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-100 disabled:opacity-50"
        >
          {copy.deleteOriginal}
        </button>
        {error && <span className="text-xs text-red-600">{error}</span>}
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      {message && <p className="text-sm text-emerald-700">{message}</p>}
      {error && <p className="text-sm text-red-700">{error}</p>}
      <label className="block">
        <span className="text-sm font-medium text-red-800">{copy.confirmationLabel}</span>
        <input
          type="text"
          value={confirmation}
          onChange={(e) => setConfirmation(e.target.value)}
          className="mt-1 block w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
          autoComplete="off"
        />
      </label>
      <button
        type="button"
        onClick={deleteAccount}
        disabled={busy}
        className="rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-50"
      >
        {copy.deleteAccount}
      </button>
    </div>
  );
}