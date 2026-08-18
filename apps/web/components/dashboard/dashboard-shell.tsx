"use client";

import React, { useState, useSyncExternalStore } from "react";
import { Sidebar } from "./sidebar";
import { MobileTopNav } from "./mobile-top-nav";

const SIDEBAR_STORAGE_KEY = "hirevia_sidebar_collapsed";

function readSidebarCollapsed(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function subscribeToSidebarCollapsed(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }
  window.addEventListener("storage", onStoreChange);
  return () => window.removeEventListener("storage", onStoreChange);
}

function getServerSidebarCollapsed(): boolean {
  return false;
}

interface DashboardShellProps {
  children: React.ReactNode;
}

export function DashboardShell({ children }: DashboardShellProps) {
  const isCollapsed = useSyncExternalStore(
    subscribeToSidebarCollapsed,
    readSidebarCollapsed,
    getServerSidebarCollapsed,
  );
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const toggleCollapse = () => {
    const next = !isCollapsed;
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
      window.dispatchEvent(new Event("storage"));
    } catch {
      // LocalStorage access may fail in private mode.
    }
  };

  return (
    <div className="min-h-screen bg-[#f4f1ea] text-[#15212b] flex flex-col">
      {/* Mobile Top Header */}
      <MobileTopNav onOpenMobile={() => setIsMobileOpen(true)} />

      {/* Persistent Left Sidebar */}
      <Sidebar
        isCollapsed={isCollapsed}
        isMobileOpen={isMobileOpen}
        onToggleCollapse={toggleCollapse}
        onCloseMobile={() => setIsMobileOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 transition-all duration-200 ease-out ${
          isCollapsed ? "lg:ml-20" : "lg:ml-64"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
