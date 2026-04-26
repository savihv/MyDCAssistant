import React from "react";

interface Props {
  className?: string;
}

export function JuniorTechBotLogo({ className = "" }: Props) {
  return (
    <div className={`relative ${className}`}>
      <svg
        viewBox="0 0 50 50"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full"
      >
        <circle cx="25" cy="25" r="23" fill="#1E293B" stroke="#3B82F6" strokeWidth="2" />
        <path
          d="M16 16H34M16 16V28M16 16L12 12M34 16V28M34 16L38 12M16 28H22M16 28L12 32M34 28H28M34 28L38 32M22 28V36L25 33L28 36V28"
          stroke="#3B82F6"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="25" cy="22" r="4" fill="#3B82F6" />
      </svg>
    </div>
  );
}
