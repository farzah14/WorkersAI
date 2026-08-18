"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";

interface SidebarRegionProps {
  isCollapsed: boolean;
}

export function SidebarRegion({ isCollapsed }: SidebarRegionProps) {
  const router = useRouter();
  const [region, setRegion] = useState<"indonesia" | "global">("indonesia");
  const [isNavigating, setIsNavigating] = useState(false);

  const handleStartSearch = () => {
    setIsNavigating(true);
    router.push("/find-jobs");
  };

  if (isCollapsed) {
    return (
      <div className="flex flex-col items-center">
        <button
          type="button"
          onClick={handleStartSearch}
          title="Find Jobs Now"
          className="w-10 h-10 flex items-center justify-center bg-[#d9623c] hover:bg-[#bb4f2e] text-white rounded-xl shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#d9623c]"
        >
          <svg
            className="w-4 h-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="p-3 bg-[#faf9f6] rounded-2xl border border-[#d9d5cc] space-y-2.5">
      {/* Region Switcher */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[#6d787e]">
          Search Region
        </span>
        <span className="text-[10px] font-mono font-medium text-[#d9623c]">
          {region === "indonesia" ? "ID" : "Global"}
        </span>
      </div>

      <div
        className="flex items-center bg-[#eae7df] p-1 rounded-xl text-xs font-medium"
        role="radiogroup"
        aria-label="Target Region"
      >
        <button
          type="button"
          onClick={() => setRegion("indonesia")}
          className={`flex-1 py-1.5 px-2 rounded-lg text-center transition-all ${
            region === "indonesia"
              ? "bg-white text-[#15212b] font-semibold shadow-xs"
              : "text-[#53616a] hover:text-[#15212b]"
          }`}
        >
          🇮🇩 Indonesia
        </button>
        <button
          type="button"
          onClick={() => setRegion("global")}
          className={`flex-1 py-1.5 px-2 rounded-lg text-center transition-all ${
            region === "global"
              ? "bg-white text-[#15212b] font-semibold shadow-xs"
              : "text-[#53616a] hover:text-[#15212b]"
          }`}
        >
          🌍 Global
        </button>
      </div>

      {/* Find Jobs Button */}
      <button
        type="button"
        onClick={handleStartSearch}
        disabled={isNavigating}
        className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-[#15212b] hover:bg-[#263946] disabled:opacity-75 text-white text-xs font-semibold rounded-xl transition-all shadow-xs focus:outline-none focus:ring-2 focus:ring-[#d9623c]"
      >
        <svg
          className="w-3.5 h-3.5 text-[#d9623c]"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <span>{isNavigating ? "Opening search..." : "Find Jobs Now"}</span>
      </button>
    </div>
  );
}
