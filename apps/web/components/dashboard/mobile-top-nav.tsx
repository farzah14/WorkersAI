import React from "react";
import Link from "next/link";

interface MobileTopNavProps {
  onOpenMobile: () => void;
}

export function MobileTopNav({ onOpenMobile }: MobileTopNavProps) {
  return (
    <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-[#d9d5cc] sticky top-0 z-30 shadow-xs">
      <Link href="/dashboard" className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-[#15212b] flex items-center justify-center text-white shrink-0">
          <svg
            className="w-4 h-4 text-[#d9623c]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
        </div>
        <span className="font-semibold text-sm tracking-tight text-[#15212b]">
          Hirevia
        </span>
      </Link>

      <button
        type="button"
        onClick={onOpenMobile}
        className="p-2 rounded-xl text-[#53616a] hover:text-[#15212b] hover:bg-[#eae7df] transition-colors focus:outline-none focus:ring-2 focus:ring-[#d9623c]"
        aria-label="Open Navigation Menu"
      >
        <svg
          className="w-5 h-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>
    </header>
  );
}
