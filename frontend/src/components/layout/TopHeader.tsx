"use client";

import React, { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function TopHeader({ showLogo = false }: { showLogo?: boolean }) {
  const router = useRouter();
  const [userProfile, setUserProfile] = useState<{ email: string; channel_title: string; is_pro: boolean; plan: string } | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
    const token = localStorage.getItem("jwt_token");
    if (!token) return;

    apiFetch("/api/user/me")
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error("Failed");
      })
      .then((data) => setUserProfile(data))
      .catch(() => {});
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("jwt_token");
    localStorage.removeItem("connectedChannel");
    setUserProfile(null);
    router.replace("/");
  };

  if (!isMounted) return <header className="shrink-0 h-20 border-b border-zinc-800/50 bg-[#09090b]/80 backdrop-blur-md fixed top-0 left-0 right-0 z-40"></header>;

  return (
    <header className={`shrink-0 h-20 border-b border-zinc-800/50 bg-black/50 backdrop-blur-md flex items-center justify-between px-8 ${showLogo ? "fixed top-0 left-0 right-0" : "sticky top-0"} z-50`}>
      <div className="flex items-center">
        {showLogo && (
          <div className="flex items-center gap-3 cursor-pointer group" onClick={() => router.push("/")}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-500 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(6,182,212,0.5)] group-hover:shadow-[0_0_20px_rgba(6,182,212,0.8)] transition-all">
              CF
            </div>
            <span className="text-2xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white to-zinc-400 group-hover:text-white transition-colors">
              CREATORFLOW
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-end">
        {userProfile ? (
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-base font-bold text-white shadow-inner">
                {userProfile.channel_title ? userProfile.channel_title.substring(0, 1).toUpperCase() : "U"}
              </div>
              <div className="flex flex-col">
                <span className="text-base font-black text-white flex items-center gap-2">
                  {userProfile.channel_title || "User"}
                  {userProfile.plan === "PRO" && (
                    <span className="px-1.5 py-0.5 rounded bg-gradient-to-r from-emerald-500 to-teal-500 text-[10px] font-black text-white shadow-sm">
                      PRO
                    </span>
                  )}
                </span>
                <span className="text-sm font-medium text-zinc-300">{userProfile.email}</span>
              </div>
            </div>
            <div className="w-px h-8 bg-zinc-700/50"></div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2.5 bg-zinc-800/40 hover:bg-zinc-700 hover:text-white rounded-xl text-base font-bold text-zinc-200 transition-all shadow-sm cursor-pointer"
            >
              <LogOut size={18} />
              <span>Log out</span>
            </button>
            {showLogo && (
              <button onClick={() => router.push("/dashboard")} className="ml-2 text-base font-black bg-white text-black px-6 py-2.5 rounded-full hover:bg-zinc-200 transition-colors shadow-lg cursor-pointer">
                Dashboard
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <button onClick={() => router.push("/login")} className="text-base font-bold text-zinc-200 hover:text-white transition-colors px-4 py-2 cursor-pointer">
              Log in
            </button>
            <button onClick={() => router.push("/login")} className="text-base font-black bg-white text-black px-6 py-2.5 rounded-full hover:bg-zinc-200 transition-colors shadow-lg cursor-pointer">
              Start for Free
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
