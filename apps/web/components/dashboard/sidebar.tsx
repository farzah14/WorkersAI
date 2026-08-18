"use client";

import React from "react";
import { SidebarHeader } from "./sidebar-header";
import { SidebarRegion } from "./sidebar-region";
import { SidebarNav } from "./sidebar-nav";
import { SidebarActiveCV } from "./sidebar-active-cv";
import { SidebarFooter } from "./sidebar-footer";

interface SidebarProps {
  isCollapsed: boolean;
  isMobileOpen: boolean;
  onToggleCollapse: () => void;
  onCloseMobile: () => void;
}

export function Sidebar({
  isCollapsed,
  isMobileOpen,
  onToggleCollapse,
  onCloseMobile,
}: SidebarProps) {
  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-[#15212b]/50 backdrop-blur-xs z-40 lg:hidden transition-opacity"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col bg-white border-r border-[#d9d5cc] transition-all duration-200 ease-out ${
          isCollapsed ? "w-20" : "w-64"
        } ${
          isMobileOpen
            ? "translate-x-0 w-72 shadow-2xl"
            : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Header Section */}
        <div className="flex items-center justify-between p-4 border-b border-[#eae7df]">
          <SidebarHeader isCollapsed={isCollapsed && !isMobileOpen} />
          {/* Mobile Close Button */}
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 rounded-lg text-[#6d787e] hover:bg-[#eae7df] hover:text-[#15212b] transition-colors"
            aria-label="Close menu"
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
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Scrollable Navigation & Region Controls */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-4">
          <SidebarRegion isCollapsed={isCollapsed && !isMobileOpen} />
          <SidebarNav
            isCollapsed={isCollapsed && !isMobileOpen}
            onNavClick={onCloseMobile}
          />
          <SidebarActiveCV isCollapsed={isCollapsed && !isMobileOpen} />
        </div>

        {/* Footer & Desktop Collapse Toggle */}
        <div className="p-3 border-t border-[#eae7df] space-y-2">
          <SidebarFooter isCollapsed={isCollapsed && !isMobileOpen} />

          {/* Desktop Collapse Toggle */}
          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden lg:flex items-center justify-center w-full py-2 px-3 text-xs font-semibold text-[#6d787e] hover:text-[#15212b] hover:bg-[#eae7df] rounded-xl transition-colors"
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? (
              <svg
                className="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
            ) : (
              <div className="flex items-center gap-2 w-full">
                <svg
                  className="w-4 h-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="15 18 9 12 15 6" />
                </svg>
                <span>Collapse</span>
              </div>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
