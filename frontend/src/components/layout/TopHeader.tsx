"use client";

import React, { useEffect, useState, useRef } from "react";
import { LogOut, ChevronDown, Plus, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { API_BASE_URL } from "@/lib/config";
import { switchChannel, CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";

type ChannelSummary = {
  id: number;
  channel_title: string;
  youtube_channel_id: string;
  needs_reconnect: boolean;
  is_connected: boolean;
  is_active: boolean;
};

export default function TopHeader({ showLogo = false }: { showLogo?: boolean }) {
  const router = useRouter();
  const [userProfile, setUserProfile] = useState<{ email: string; channel_title: string; is_pro: boolean; plan: string } | null>(null);
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [maxChannels, setMaxChannels] = useState(1);
  const [isMounted, setIsMounted] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  // isSwitching(state)만으로 중복 클릭을 막으면, setIsSwitching(true)가 실제로 반영되는(리렌더되는)
  // 시점까지의 짧은 틈에 두 번째 클릭이 여전히 isSwitching===false로 통과해버릴 수 있다.
  // ref는 즉시(동기적으로) 갱신되므로 이 틈을 없앤다.
  const isSwitchingRef = useRef(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  const loadAccountInfo = () => {
    apiFetch("/api/user/me")
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error("Failed");
      })
      .then((data) => setUserProfile(data))
      .catch(() => {});

    apiFetch("/api/channels")
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error("Failed");
      })
      .then((data) => {
        setChannels(data.channels || []);
        setMaxChannels(data.max_channels ?? 1);
      })
      .catch(() => {});
  };

  useEffect(() => {
    setIsMounted(true);
    const token = localStorage.getItem("jwt_token");
    if (!token) return;
    loadAccountInfo();
  }, []);

  // 채널 전환은 이 컴포넌트의 드롭다운뿐 아니라 각 페이지의 좌측 상단 select box에서도 일어날 수
  // 있으므로, 전환 이벤트를 구독해서 헤더에 표시되는 계정 정보(이름/PRO 여부/채널 목록)를 갱신한다.
  useEffect(() => {
    const handleChannelSwitched = () => loadAccountInfo();
    window.addEventListener(CHANNEL_SWITCHED_EVENT, handleChannelSwitched);
    return () => window.removeEventListener(CHANNEL_SWITCHED_EVENT, handleChannelSwitched);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!isMenuOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsMenuOpen(false);
        menuButtonRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMenuOpen]);

  const handleLogout = () => {
    localStorage.removeItem("jwt_token");
    localStorage.removeItem("connectedChannel");
    setUserProfile(null);
    router.replace("/");
  };

  const handleSwitchChannel = async (channelId: number) => {
    if (isSwitchingRef.current) return;
    isSwitchingRef.current = true;
    setIsSwitching(true);
    const ok = await switchChannel(channelId);
    // 성공/실패 관계없이 여기서 끝난다 - 성공 시 CHANNEL_SWITCHED_EVENT를 구독 중인 이 컴포넌트와
    // 각 페이지가 알아서 최신 데이터를 다시 불러온다 (더 이상 페이지 새로고침 없음).
    if (ok) setIsMenuOpen(false);
    isSwitchingRef.current = false;
    setIsSwitching(false);
  };

  const handleConnectAnother = () => {
    // 지금 로그인된 유저의 JWT를 state로 실어 보내야, 콜백에서 새 채널을
    // (구글 로그인이 다른 계정/브랜드 계정으로 이뤄지더라도) 지금 이 유저 소유로 붙일 수 있다.
    // 안 실어 보내면 완전히 새로운 유저가 생겨서 기존 계정이 사라진 것처럼 보이는 버그가 생긴다.
    const currentToken = localStorage.getItem("jwt_token");
    const stateParam = currentToken ? `?state=${encodeURIComponent(currentToken)}` : "";
    window.location.href = `${API_BASE_URL}/api/auth/login${stateParam}`;
  };

  if (!isMounted) return <header className="shrink-0 h-20 border-b border-zinc-800/50 bg-[#09090b]/80 backdrop-blur-md fixed top-0 left-0 right-0 z-40"></header>;

  const atChannelLimit = channels.length >= maxChannels;

  return (
    <header className={`shrink-0 h-20 border-b border-zinc-800/50 bg-black/50 backdrop-blur-md flex items-center justify-between px-8 ${showLogo ? "fixed top-0 left-0 right-0" : "sticky top-0"} z-50`}>
      <div className="flex items-center">
        {showLogo && (
          <Link href="/" className="flex items-center gap-3 group rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-500 flex items-center justify-center font-bold text-white shadow-[0_0_15px_rgba(6,182,212,0.5)] group-hover:shadow-[0_0_20px_rgba(6,182,212,0.8)] transition-all" aria-hidden="true">
              CF
            </div>
            <span className="text-2xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white to-zinc-400 group-hover:text-white transition-colors">
              CREATORFLOW
            </span>
          </Link>
        )}
      </div>

      <div className="flex items-center justify-end">
        {userProfile ? (
          <div className="flex items-center gap-6">
            <div className="relative" ref={menuRef}>
              <button
                ref={menuButtonRef}
                onClick={() => setIsMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={isMenuOpen}
                aria-controls="channel-switcher-menu"
                className="flex items-center gap-3 cursor-pointer group rounded-xl px-2 py-1.5 hover:bg-zinc-800/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <div className="w-11 h-11 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-base font-bold text-white shadow-inner flex-shrink-0" aria-hidden="true">
                  {userProfile.channel_title ? userProfile.channel_title.substring(0, 1).toUpperCase() : "U"}
                </div>
                <div className="flex flex-col items-start">
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
                <ChevronDown size={18} aria-hidden="true" className={`text-zinc-400 transition-transform ${isMenuOpen ? "rotate-180" : ""}`} />
              </button>

              {isMenuOpen && (
                <div id="channel-switcher-menu" role="menu" aria-label="연동된 채널 전환" className="absolute right-0 top-full mt-2 w-80 bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden z-50">
                  <div className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-zinc-400 border-b border-zinc-800">
                    연동된 채널 ({channels.length}/{maxChannels})
                  </div>
                  <div className="max-h-72 overflow-y-auto">
                    {channels.map((c) => (
                      <button
                        key={c.id}
                        role="menuitem"
                        onClick={() => !c.is_active && handleSwitchChannel(c.id)}
                        disabled={isSwitching}
                        aria-current={c.is_active ? "true" : undefined}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-400 ${c.is_active ? "bg-cyan-500/10" : "hover:bg-zinc-800/60 cursor-pointer"} disabled:opacity-60`}
                      >
                        <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-sm font-bold text-zinc-300 flex-shrink-0" aria-hidden="true">
                          {c.channel_title ? c.channel_title.substring(0, 1).toUpperCase() : "?"}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-bold text-white truncate">{c.channel_title || "이름 없음"}</div>
                          {!c.is_connected ? (
                            <div className="text-xs text-zinc-500">연동 해제됨</div>
                          ) : c.needs_reconnect ? (
                            <div className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle size={11} aria-hidden="true" /> 재연동 필요</div>
                          ) : null}
                        </div>
                        {c.is_active && <span className="text-xs font-bold text-cyan-400">사용 중</span>}
                      </button>
                    ))}
                  </div>
                  <button
                    role="menuitem"
                    onClick={handleConnectAnother}
                    disabled={atChannelLimit}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left text-sm font-bold text-zinc-300 hover:bg-zinc-800/60 border-t border-zinc-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-400"
                    title={atChannelLimit ? "요금제의 채널 연동 한도에 도달했습니다" : ""}
                  >
                    <Plus size={16} className="text-cyan-400" aria-hidden="true" />
                    {atChannelLimit ? "채널 연동 한도 도달 (업그레이드 필요)" : "다른 채널 연동하기"}
                  </button>
                </div>
              )}
            </div>

            <div className="w-px h-8 bg-zinc-700/50" aria-hidden="true"></div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2.5 bg-zinc-800/40 hover:bg-zinc-700 hover:text-white rounded-xl text-base font-bold text-zinc-200 transition-all shadow-sm cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            >
              <LogOut size={18} aria-hidden="true" />
              <span>Log out</span>
            </button>
            {showLogo && (
              <button onClick={() => router.push("/dashboard")} className="ml-2 text-base font-black bg-white text-black px-6 py-2.5 rounded-full hover:bg-zinc-200 transition-colors shadow-lg cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-black">
                Dashboard
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <button onClick={() => router.push("/login")} className="text-base font-bold text-zinc-200 hover:text-white transition-colors px-4 py-2 cursor-pointer rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              Log in
            </button>
            <button onClick={() => router.push("/login")} className="text-base font-black bg-white text-black px-6 py-2.5 rounded-full hover:bg-zinc-200 transition-colors shadow-lg cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-black">
              Start for Free
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
