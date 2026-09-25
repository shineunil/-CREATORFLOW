"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import TopHeader from "./TopHeader";
import AnnouncementPopup from "@/components/AnnouncementPopup";
import { API_BASE_URL } from "@/lib/config";
import { isPublicPath, stripLocalePrefix } from "@/i18n/config";
import { useI18n } from "@/i18n/I18nProvider";

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, lp } = useI18n();
  const [isAuthChecked, setIsAuthChecked] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  // 한국어 공개 페이지는 브라우저 주소가 /ko/... 이므로 앞부분을 떼고 비교한다.
  const path = stripLocalePrefix(pathname).path;
  const isNoSidebarPage = isPublicPath(path);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);

    // 구 버전 호환: ?token=xxx (이전 배포에서 발급된 URL이 남아있을 경우)
    const urlToken = searchParams.get("token");
    if (urlToken) {
      // 구 토큰은 백엔드로 exchange해서 쿠키로 전환할 수 없으므로 그냥 로그인 페이지로 보낸다.
      window.history.replaceState({}, document.title, pathname);
      router.replace(lp("/login"));
      return;
    }

    if (isNoSidebarPage) {
      setIsAuthChecked(true);
      return;
    }

    // C-1: auth_code가 있으면 exchange 엔드포인트로 교환 — 성공 시 백엔드가 HttpOnly 쿠키를 설정한다.
    const authCode = searchParams.get("auth_code");
    if (authCode) {
      (async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/auth/exchange?code=${encodeURIComponent(authCode)}`,
            { credentials: "include" }
          );
          if (res.ok) {
            // L-3: 토큰은 HttpOnly 쿠키에 있음. isLoggedIn은 로그인 상태 UX 힌트용.
            localStorage.setItem("isLoggedIn", "1");
            const ch = searchParams.get("connected_channel");
            if (ch) localStorage.setItem("connectedChannel", ch);
          }
        } catch {
          // exchange 실패 — 로그인 페이지로
        }
        window.history.replaceState({}, document.title, pathname);
        const loggedIn = localStorage.getItem("isLoggedIn");
        if (!loggedIn) router.replace(lp("/login"));
        else setIsAuthChecked(true);
      })();
      return;
    }

    // 일반 경우: isLoggedIn 힌트 확인 (실제 인증은 쿠키로, 이건 UX용 빠른 확인)
    const loggedIn = localStorage.getItem("isLoggedIn");
    if (!loggedIn) {
      router.replace(lp("/login"));
    } else {
      setIsAuthChecked(true);
    }
  }, [pathname, isNoSidebarPage, router, lp]);

  if (!isAuthChecked) {
    return (
      <div className="flex h-screen w-full bg-[#09090b] items-center justify-center" role="status">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" aria-hidden="true" />
        <span className="sr-only">{t.common.loading}</span>
      </div>
    );
  }

  if (isNoSidebarPage) {
    return (
      <div className="flex-1 flex flex-col relative overflow-y-auto w-full min-h-screen bg-[#09090b] text-zinc-100 font-sans">
        {path === "/" && <TopHeader showLogo={true} />}
        <main>{children}</main>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full bg-[#09090b] text-zinc-100 overflow-hidden font-sans">
      <Sidebar isOpen={isMobileMenuOpen} onClose={() => setIsMobileMenuOpen(false)} />
      <div className="flex-1 flex flex-col relative overflow-y-auto min-w-0">
        <TopHeader onMenuClick={() => setIsMobileMenuOpen(true)} />
        <main>{children}</main>
      </div>
      <AnnouncementPopup />
    </div>
  );
}
