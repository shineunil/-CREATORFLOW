"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import TopHeader from "./TopHeader";
import AnnouncementPopup from "@/components/AnnouncementPopup";
import { API_BASE_URL } from "@/lib/config";

// 로그인 없이 접근 가능한 공개 페이지 목록
// (개인정보처리방침/이용약관은 로그인 여부와 무관하게 항상 접근 가능해야 함 - 구글 OAuth 심사 요건)
const PUBLIC_PATHS = ["/", "/login", "/privacy", "/terms", "/pricing-public"];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthChecked, setIsAuthChecked] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const isNoSidebarPage = PUBLIC_PATHS.includes(pathname);

  // 페이지를 이동할 때마다(모바일 메뉴에서 링크 클릭 등) 열려있던 모바일 사이드바를 자동으로 닫는다.
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);

    // 구 버전 호환: ?token=xxx (이전 배포에서 발급된 URL이 남아있을 경우)
    const urlToken = searchParams.get("token");
    if (urlToken) {
      localStorage.setItem("jwt_token", urlToken);
      const ch = searchParams.get("connected_channel");
      if (ch) localStorage.setItem("connectedChannel", ch);
      window.history.replaceState({}, document.title, pathname);
    }

    // 공개 페이지는 인증 체크 불필요
    if (isNoSidebarPage) {
      setIsAuthChecked(true);
      return;
    }

    // C-1: auth_code가 있으면 exchange 엔드포인트로 교환 후 인증 체크
    // (exchange는 비동기이므로 완료될 때까지 로딩 스피너를 유지한다)
    const authCode = searchParams.get("auth_code");
    if (authCode) {
      (async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/auth/exchange?code=${encodeURIComponent(authCode)}`
          );
          if (res.ok) {
            const data = await res.json();
            if (data?.token) {
              localStorage.setItem("jwt_token", data.token);
              const ch = searchParams.get("connected_channel");
              if (ch) localStorage.setItem("connectedChannel", ch);
            }
          }
        } catch {
          // exchange 실패 — 토큰 없음으로 처리
        }
        // auth_code + connected_channel을 URL에서 제거
        window.history.replaceState({}, document.title, pathname);
        const token = localStorage.getItem("jwt_token");
        if (!token) router.replace("/login");
        else setIsAuthChecked(true);
      })();
      return; // exchange 완료 전까지 대기 (스피너 표시)
    }

    // 일반 경우: localStorage에서 토큰 확인
    const token = localStorage.getItem("jwt_token");
    if (!token) {
      router.replace("/login");
    } else {
      setIsAuthChecked(true);
    }
  }, [pathname, isNoSidebarPage, router]);

  // 인증 확인 전 빈 화면 대신 로딩 스피너 표시 (깜빡임 방지)
  if (!isAuthChecked) {
    return (
      <div className="flex h-screen w-full bg-[#09090b] items-center justify-center" role="status">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" aria-hidden="true" />
        <span className="sr-only">로딩 중...</span>
      </div>
    );
  }

  if (isNoSidebarPage) {
    return (
      <div className="flex-1 flex flex-col relative overflow-y-auto w-full min-h-screen bg-[#09090b] text-zinc-100 font-sans">
        {pathname === "/" && <TopHeader showLogo={true} />}
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
