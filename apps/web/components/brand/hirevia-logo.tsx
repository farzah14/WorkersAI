import React from "react";

interface HireviaLogoProps {
  isCollapsed?: boolean;
  className?: string;
}

export function HireviaLogo({ isCollapsed = false, className = "" }: HireviaLogoProps) {
  return (
    <div className={`flex items-center gap-2.5 overflow-hidden ${className}`}>
      {/* Concept 2 Brand Mark: Clean bold orange ribbon + signals + black briefcase */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="10 45 410 305"
        className="w-8 h-8 shrink-0"
        role="img"
        aria-hidden="true"
      >
        <g>
          {/* Signal traces */}
          <g stroke="#d9623c" strokeWidth="11" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.85">
            <path d="M 34 66 H 91 L 119 91" />
            <path d="M 20 103 H 79 L 103 127 H 119" />
            <path d="M 47 143 H 93 L 113 160 H 122" />
          </g>
          {/* Signal dots */}
          <g fill="#d9623c">
            <circle cx="34" cy="66" r="14" />
            <circle cx="20" cy="103" r="14" />
            <circle cx="47" cy="143" r="14" />
          </g>
          {/* Rising career wave ribbon - solid brand orange for 100% reliable rendering */}
          <path
            d="M 80 175 L 127 281 Q 135 299 146 279 L 201 175 Q 213 154 227 177 L 288 282 L 357 141"
            fill="none"
            stroke="#d9623c"
            strokeWidth="48"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Directional arrow */}
          <path d="M 334 119 L 385 118 L 371 169 Z" fill="#d9623c" />
          {/* Focus node */}
          <circle cx="211" cy="102" r="34" fill="#d9623c" />
          {/* Black Briefcase with orange latch */}
          <g transform="translate(300 240)">
            <rect x="0" y="25" width="108" height="77" rx="14" fill="#15212b" />
            <path d="M 31 28 V 16 Q 31 8 39 8 H 70 Q 78 8 78 16 V 28" stroke="#15212b" strokeWidth="12" strokeLinecap="round" fill="none" />
            <path d="M 0 52 L 42 75 H 66 L 108 52" stroke="#FFFFFF" strokeOpacity="0.8" strokeWidth="6" fill="none" />
            <rect x="47" y="69" width="16" height="17" rx="4" fill="#d9623c" />
          </g>
        </g>
      </svg>

      {!isCollapsed && (
        <span className="font-bold text-xl tracking-tight text-[#15212b] leading-none">
          Hire<span className="text-[#d9623c]">via</span>
        </span>
      )}
    </div>
  );
}
