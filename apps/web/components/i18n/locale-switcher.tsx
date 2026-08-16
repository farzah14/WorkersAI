"use client";

import { useRouter } from "next/navigation";

export function LocaleSwitcher({ locale }: { locale: "id" | "en" }) {
  const router = useRouter();

  async function switchLocale(next: "id" | "en") {
    document.cookie = `locale=${next};path=/;max-age=31536000;samesite=lax`;
    await fetch("/api/locale", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale: next }),
    }).catch(() => undefined);
    router.refresh();
  }

  const active =
    "rounded-full bg-[#15212b] px-3 py-1.5 text-xs font-bold text-white";
  const inactive =
    "rounded-full px-3 py-1.5 text-xs font-semibold text-[#6d787e] transition hover:text-[#15212b]";

  return (
    <div
      aria-label="Language"
      className="fixed right-5 top-5 z-50 flex items-center gap-1 rounded-full border border-[#d9d5cc] bg-white/90 p-1 shadow-sm backdrop-blur"
    >
      <button type="button" className={locale === "id" ? active : inactive} onClick={() => switchLocale("id")}>
        ID
      </button>
      <button type="button" className={locale === "en" ? active : inactive} onClick={() => switchLocale("en")}>
        EN
      </button>
    </div>
  );
}