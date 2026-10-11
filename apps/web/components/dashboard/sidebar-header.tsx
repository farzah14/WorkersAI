import React from "react";
import Link from "next/link";
import { HireviaLogo } from "@/components/brand/hirevia-logo";

interface SidebarHeaderProps {
  isCollapsed: boolean;
}

export function SidebarHeader({ isCollapsed }: SidebarHeaderProps) {
  return (
    <Link
      href="/dashboard"
      className="flex items-center gap-2 overflow-hidden group focus:outline-none focus:ring-2 focus:ring-[#d9623c] rounded-xl p-0.5"
      aria-label="Hirevia Dashboard"
    >
      <HireviaLogo isCollapsed={isCollapsed} />
    </Link>
  );
}
