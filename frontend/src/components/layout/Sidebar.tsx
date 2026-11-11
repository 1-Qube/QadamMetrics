"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGrid,
  Database,
  BookOpen,
  Network,
  BookMarked,
  Sliders,
  FileText,
  Settings,
  Sparkles,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { label: "Overview", href: "/", icon: LayoutGrid },
  { label: "Data", href: "/data", icon: Database },
  { label: "Topics", href: "/topics", icon: BookOpen },
  { label: "Knowledge Map", href: "/knowledge-map", icon: Network },
  { label: "Textbooks", href: "/textbooks", icon: BookMarked },
  { label: "Planning", href: "/planning", icon: Sliders },
  { label: "Reports", href: "/reports", icon: FileText },
  { label: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 min-h-screen bg-[#FAF9F6] border-r border-[#E6E5E0] flex flex-col justify-between select-none shrink-0">
      <div>
        {/* Brand Header */}
        <div className="p-6 pb-8 flex items-center gap-3">
          <div className="w-8 h-8 bg-[#151515] flex items-center justify-center rounded-sm text-white shadow-sm">
            <svg
              viewBox="0 0 24 24"
              className="w-5 h-5 fill-current"
              xmlns="http://www.w3.org/2000/svg"
            >
              <polygon points="4,4 12,4 4,20" />
              <polygon points="12,4 20,20 12,20" />
            </svg>
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight text-[#151515]">
              QadamMetrics
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="px-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? "bg-[#C9F542] text-[#151515] shadow-sm font-semibold"
                    : "text-[#70706B] hover:text-[#151515] hover:bg-[#F3F2EE]"
                }`}
              >
                <Icon
                  className={`w-4 h-4 ${
                    isActive ? "text-[#151515]" : "text-[#95958E]"
                  }`}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Branding & Graphic */}
      <div className="p-6 pt-0 relative overflow-hidden">
        <div className="mb-4 text-xs font-serif leading-relaxed text-[#70706B]">
          <span className="block font-medium text-[#151515]">Smarter decisions.</span>
          <span>Better education.</span>
        </div>

        {/* Editorial Mountain Illustration matching reference image */}
        <div className="w-full h-16 relative opacity-70">
          <svg
            viewBox="0 0 200 60"
            className="w-full h-full text-[#D1D0C9]"
            preserveAspectRatio="none"
          >
            <polygon points="0,60 40,25 90,60" fill="#EAE8E3" />
            <polygon points="30,60 70,12 120,60" fill="#DCDAD3" />
            <polygon points="60,60 110,20 160,60" fill="#CECCC4" />
            <polygon points="100,60 145,15 190,60" fill="#E2E0D9" />
            <polygon points="130,60 175,28 200,60" fill="#D4D2CA" />
          </svg>
        </div>
      </div>
    </aside>
  );
}
