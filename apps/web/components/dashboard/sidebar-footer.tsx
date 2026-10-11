"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { initialsFor, resolveDisplayName } from "@/lib/display-name";

interface SidebarFooterProps {
  isCollapsed: boolean;
}

export function SidebarFooter({ isCollapsed }: SidebarFooterProps) {
  const router = useRouter();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [displayName, setDisplayName] = useState("Job Seeker");
  const [initials, setInitials] = useState("JS");

  useEffect(() => {
    let cancelled = false;
    createClient()
      .auth.getUser()
      .then(({ data }) => {
        if (cancelled) return;
        const name = resolveDisplayName(data.user);
        setDisplayName(name);
        setInitials(initialsFor(name));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSignOut() {
    setIsSigningOut(true);
    const supabase = createClient();
    await supabase.auth.signOut().catch(() => undefined);
    router.push("/login");
    router.refresh();
  }


  if (isCollapsed) {
    return (
      <div className="flex flex-col items-center gap-2 pt-2">
        <button
          type="button"
          onClick={handleSignOut}
          title="Sign out"
          className="p-2 text-[#6d787e] hover:text-[#d9623c] hover:bg-[#eae7df] rounded-xl transition-colors"
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
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3 pt-2">
      {/* User Session & Logout */}
      <div className="flex items-center justify-between p-2 rounded-xl bg-[#faf9f6] border border-[#d9d5cc]">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-full bg-[#15212b] text-white flex items-center justify-center font-mono font-bold text-xs shrink-0">
            {initials}
          </div>
          <div className="truncate">
            <p className="text-xs font-semibold text-[#15212b] truncate">
              {displayName}
            </p>
            <p className="text-[10px] text-[#6d787e] truncate font-mono">
              Signed in
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleSignOut}
          disabled={isSigningOut}
          className="p-1.5 text-[#6d787e] hover:text-[#d9623c] rounded-lg hover:bg-[#eae7df] transition-colors"
          title="Sign out"
          aria-label="Sign out"
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
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
