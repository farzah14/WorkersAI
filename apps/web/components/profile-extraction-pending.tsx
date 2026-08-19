"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function ProfileExtractionPending({ cvName }: { cvName: string }) {
  const router = useRouter();

  useEffect(() => {
    const refreshTimer = window.setInterval(() => router.refresh(), 1500);
    return () => window.clearInterval(refreshTimer);
  }, [router]);

  return (
    <section
      aria-busy="true"
      aria-live="polite"
      className="rounded border border-blue-200 bg-blue-50 p-5 text-blue-900"
    >
      <h2 className="font-semibold">Building your candidate profile</h2>
      <p className="mt-2 text-sm">
        {cvName} has been extracted. We are structuring the profile now. This page will update automatically.
      </p>
    </section>
  );
}
