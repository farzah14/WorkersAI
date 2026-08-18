"use client";

import { usePathname, useRouter } from "next/navigation";

export function LocaleSwitcher({ locale }: { locale: "id" | "en" }) {
  const router = useRouter();
  const isLandingPage = usePathname() === "/";

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
    "px-1.5 py-1 text-xs font-bold text-[#15212b] underline underline-offset-4 decoration-2 decoration-[#d9623c] transition";
  const inactive =
    "px-1.5 py-1 text-xs font-medium text-[#6d787e] transition hover:text-[#15212b]";

  return (
    <div
      aria-label="Language"
      className={`fixed right-5 top-5 z-50 flex items-center gap-1 font-mono text-xs ${
        isLandingPage ? "max-[40rem]:top-20" : ""
      }`}
    >
      <button
        type="button"
        className={locale === "id" ? active : inactive}
        onClick={() => switchLocale("id")}
      >
        ID
      </button>
      <span className="text-[#d9d5cc] select-none" aria-hidden="true">
        /
      </span>
      <button
        type="button"
        className={locale === "en" ? active : inactive}
        onClick={() => switchLocale("en")}
      >
        EN
      </button>
    </div>
  );
}
