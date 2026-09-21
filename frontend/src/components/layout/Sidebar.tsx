"use client";

import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  FolderOpen,
  BarChart3,
  History,
  Settings,
  CreditCard,
  Bell,
  MoreHorizontal,
  LogOut,
  ShieldAlert,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { apiFetch } from "@/lib/api";

const MENUS = [
  { name: "Dashboard", icon: LayoutDashboard, href: "/dashboard" },
  { name: "New Test", icon: FolderOpen, href: "/new" },
  { name: "Analytics", icon: BarChart3, href: "/analytics" },
  { name: "History", icon: History, href: "/history" },
  { name: "Pricing", icon: CreditCard, href: "/pricing" },
  { name: "Settings", icon: Settings, href: "/settings" },
];

export default function Sidebar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const pathname = usePathname();

  const [userProfile, setUserProfile] = React.useState<{ email: string | null; plan: string; is_pro: boolean; channel_title: string | null; is_admin: boolean }>({
    email: null,
    plan: "BASIC",
    is_pro: false,
    channel_title: null,
    is_admin: false
  });

  React.useEffect(() => {
    // 상단에서 이미 import된 apiFetch 직접 사용
    apiFetch("/api/user/me")
      .then(res => {
        if (!res.ok) throw new Error(`Failed to load profile (${res.status})`);
        return res.json();
      })
      .then(data => {
        setUserProfile({
          email: data.email,
          plan: data.plan,
          is_pro: data.is_pro,
          channel_title: data.channel_title,
          is_admin: !!data.is_admin
        });
      })
      .catch(console.error);
  }, []);

  const menus = userProfile.is_admin
    ? [...MENUS, { name: "Admin", icon: ShieldAlert, href: "/admin" }]
    : MENUS;

  return (
    <>
      {/* 모바일에서 사이드바가 열려있을 때만 보이는 배경 딤 처리 - 탭하면 닫힘 */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-[55] md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed md:static inset-y-0 left-0 w-64 flex-shrink-0 border-r border-zinc-800/50 bg-[#000000] h-screen p-6 flex flex-col z-[60] md:z-50 transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        } md:translate-x-0`}
      >
        <div className="flex items-center justify-between mb-10">
          <Link href="/" className="flex items-center gap-2 px-2 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            <div className="w-8 h-8 rounded bg-gradient-to-tr from-cyan-500 to-blue-500 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(6,182,212,0.5)]" aria-hidden="true">
              TF
            </div>
            <span className="text-xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white to-zinc-400">THUMBNAILFLOW</span>
          </Link>
          <button
            onClick={onClose}
            aria-label="메뉴 닫기"
            className="md:hidden p-1.5 text-zinc-400 hover:text-white rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto" aria-label="주 메뉴">
          {menus.map((menu) => {
            // exact match OR sub-routes
            const isActive = pathname === menu.href || pathname.startsWith(`${menu.href}/`);
            return (
              <Link
                key={menu.name}
                href={menu.href}
                onClick={onClose}
                aria-current={isActive ? "page" : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                  isActive
                    ? "bg-zinc-900 text-white shadow-sm"
                    : "text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200"
                }`}
              >
                <menu.icon
                  size={18}
                  aria-hidden="true"
                  className={isActive ? "text-cyan-400" : "text-zinc-400"}
                />
                {menu.name}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto">
          <div className="p-4 rounded-2xl bg-zinc-900/50 border border-zinc-800">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                Your Plan
              </span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${userProfile.is_pro ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-400" : "border-zinc-700 bg-zinc-800 text-zinc-400"}`}>
                {userProfile.plan}
              </span>
            </div>
            <div className="text-sm font-semibold mb-1">
              {userProfile.is_pro ? "Unlimited active tests" : "1 active test limit"}
            </div>
            <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden mt-3" aria-hidden="true">
              <div className={`h-full ${userProfile.is_pro ? "bg-cyan-500 w-full" : "bg-zinc-500 w-[100%]"}`} />
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
