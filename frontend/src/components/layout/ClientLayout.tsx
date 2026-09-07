"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import TopHeader from "./TopHeader";

// 로그인 없이 접근 가능한 공개 페이지 목록
// (개인정보처리방침/이용약관은 로그인 여부와 무관하게 항상 접근 가능해야 함 - 구글 OAuth 심사 요건)
const PUBLIC_PATHS = ["/", "/login", "/privacy", "/terms"];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAuthChecked, setIsAuthChecked] = useState(false);
  const isNoSidebarPage = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    // 1. URL에 새로 발급받은 토큰이 있다면 먼저 저장소에 저장
    const searchParams = new URLSearchParams(window.location.search);
    const urlToken = searchParams.get("token");
    if (urlToken) {
      localStorage.setItem("jwt_token", urlToken);
      const channelFromUrl = searchParams.get("connected_channel");
      if (channelFromUrl) {
        localStorage.setItem("connectedChannel", channelFromUrl);
      }
      // 저장 후 URL에서 파라미터 제거 (보안 및 깔끔한 URL 유지)
      window.history.replaceState({}, document.title, pathname);
    }

    // 2. 공개 페이지는 인증 체크 불필요
    if (isNoSidebarPage) {
      setIsAuthChecked(true);
      return;
    }

    // 3. 보호된 페이지: 토큰 유무 확인
    const token = localStorage.getItem("jwt_token");
    if (!token) {
      // 토큰 없으면 로그인 페이지로 즉시 이동
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
      <Sidebar />
      <div className="flex-1 flex flex-col relative overflow-y-auto">
        <TopHeader />
        <main>{children}</main>
      </div>
    </div>
  );
}
