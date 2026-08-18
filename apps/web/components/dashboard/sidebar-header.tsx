import React from "react";
import Link from "next/link";

interface SidebarHeaderProps {
  isCollapsed: boolean;
}

export function SidebarHeader({ isCollapsed }: SidebarHeaderProps) {
  return (
    <Link
      href="/dashboard"
      className="flex items-center gap-3 overflow-hidden group focus:outline-none focus:ring-2 focus:ring-[#d9623c] rounded-xl p-1"
    >
      <div className="w-9 h-9 rounded-xl bg-[#15212b] group-hover:bg-[#263946] flex items-center justify-center text-white shrink-0 shadow-sm transition-colors">
        <svg
          className="w-5 h-5 text-[#d9623c]"
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

      {!isCollapsed && (
        <div className="flex flex-col min-w-0">
          <span className="font-semibold text-base tracking-tight text-[#15212b] truncate">
            Hirevia
          </span>
          <span className="text-[10px] font-mono font-medium tracking-wider uppercase text-[#d9623c]">
            Job Matcher MVP
          </span>
        </div>
      )}
    </Link>
  );
}
