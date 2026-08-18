import React from "react";
import Link from "next/link";

interface SidebarActiveCVProps {
  isCollapsed: boolean;
}

export function SidebarActiveCV({ isCollapsed }: SidebarActiveCVProps) {
  if (isCollapsed) {
    return (
      <div className="flex justify-center">
        <Link
          href="/dashboard/profile"
          title="Active CV: Ready"
          className="w-8 h-8 rounded-lg bg-[#e5f0ec] flex items-center justify-center text-[#1f6b59] hover:bg-[#d2e7e0] transition-colors"
        >
          <svg
            className="w-4 h-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </Link>
      </div>
    );
  }

  return (
    <div className="p-3 bg-[#faf9f6] rounded-2xl border border-[#d9d5cc] space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[#6d787e]">
          Active Profile
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#1f6b59] bg-[#e5f0ec] px-2 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-[#1f6b59]" />
          Ready
        </span>
      </div>

      <Link
        href="/dashboard/profile"
        className="flex items-center gap-2 text-xs font-medium text-[#15212b] hover:text-[#d9623c] transition-colors group"
      >
        <svg
          className="w-4 h-4 text-[#6d787e] group-hover:text-[#d9623c] shrink-0 transition-colors"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
        <span className="truncate">Active Digital CV</span>
      </Link>
    </div>
  );
}
