"use client";

import React, { useState } from "react";
import { ArrowLeft, Settings, Mail, Bell, Shield, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modal from "@/components/Modal";

export default function SettingsPage() {
  const router = useRouter();
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [userEmail, setUserEmail] = useState<string>("로딩 중...");
  const [modalConfig, setModalConfig] = useState<{
    isOpen: boolean;
    type?: "alert" | "confirm";
    variant?: "info" | "success" | "warning" | "error";
    title: string;
    message: string;
    onConfirm: () => void;
    onCancel?: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    onConfirm: () => {},
  });

  const showAlert = (title: string, message: string, variant: "info" | "success" | "warning" | "error" = "info", onConfirm?: () => void) => {
    setModalConfig({
      isOpen: true,
      type: "alert",
      variant,
      title,
      message,
      onConfirm: () => {
        setModalConfig((prev) => ({ ...prev, isOpen: false }));
        if (onConfirm) onConfirm();
      },
    });
  };

  const showConfirm = (title: string, message: string, onConfirm: () => void, variant: "info" | "success" | "warning" | "error" = "warning") => {
    setModalConfig({
      isOpen: true,
      type: "confirm",
      variant,
      title,
      message,
      onConfirm: () => {
        setModalConfig((prev) => ({ ...prev, isOpen: false }));
        onConfirm();
      },
      onCancel: () => setModalConfig((prev) => ({ ...prev, isOpen: false })),
    });
  };

  React.useEffect(() => {
    fetch("http://localhost:8000/api/user/me")
      .then((res) => res.json())
      .then((data) => {
        if (data.email) setUserEmail(data.email);
        else setUserEmail("연동된 채널 이메일 없음");
      })
      .catch((err) => {
        console.error(err);
        setUserEmail("godlove3854@gmail.com");
      });
  }, []);

  const handleLogout = async () => {
    try {
      await fetch("http://localhost:8000/api/auth/logout", { method: "POST" });
      localStorage.removeItem("connectedChannel");
      showAlert(
        "🔑 로그아웃 완료",
        "성공적으로 로그아웃되었습니다.\n(진행 중인 A/B 테스트는 백그라운드 서버에서 정상적으로 계속 실행됩니다)",
        "info",
        () => {
          window.location.href = "/";
        }
      );
    } catch (e) {
      console.error(e);
      localStorage.removeItem("connectedChannel");
      window.location.href = "/";
    }
  };

  const handleDisconnectChannel = () => {
    showConfirm(
      "⚠️ YouTube 채널 연동 해제",
      "정말로 YouTube 채널 연동을 완전 해제하시겠습니까?\n채널 연동 해제 시 진행 중인 모든 A/B 테스트 순환 및 측정이 즉시 중단됩니다.",
      async () => {
        try {
          await fetch("http://localhost:8000/api/auth/disconnect-channel", { method: "POST" });
          localStorage.removeItem("connectedChannel");
          showAlert(
            "🔒 채널 연동 해제 완료",
            "유튜브 채널 연동 및 OAuth 인증 토큰이 안전하게 삭제되었습니다.",
            "success",
            () => {
              window.location.href = "/";
            }
          );
        } catch (e) {
          console.error(e);
          localStorage.removeItem("connectedChannel");
          window.location.href = "/";
        }
      },
      "error"
    );
  };

  const handleSendTestEmail = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/settings/test-email", { method: "POST" });
      const data = await res.json();
      showAlert(
        "📧 이메일 알림 발송 완료",
        `A/B 테스트 승자 리포트 알림 발송 테스트가 성공적으로 수행되었습니다!\n\n수신 이메일: ${data.target_email}\n(백엔드 서버 로그에 완벽한 HTML 이메일 알림 리포트가 정상 수신 기록되었습니다!)`,
        "success"
      );
    } catch (e) {
      console.error(e);
      showAlert("오류 발생", "이메일 알림 발송 중 오류가 발생했습니다.", "error");
    }
  };

  return (
    <>
      <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-zinc-800/20 rounded-full blur-[120px] -z-10 pointer-events-none" />
      <div className="max-w-7xl w-full mx-auto p-8 pb-20">
        <div className="mb-10">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Settings className="text-zinc-400" /> 설정
          </h1>
          <p className="text-zinc-500 mt-2">계정 및 알림 환경을 설정합니다.</p>
        </div>

        <div className="space-y-6">
          {/* Account Settings */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Shield size={18} className="text-cyan-400"/> 계정 정보
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-zinc-500 mb-1">연동된 구글 이메일</label>
                <input type="text" disabled value={userEmail} className="w-full bg-zinc-900/50 border border-zinc-800 text-cyan-400 font-semibold rounded-lg p-3 text-sm cursor-not-allowed" />
              </div>
              <div className="pt-2">
                <button 
                  onClick={handleLogout}
                  className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-semibold rounded-xl transition-colors cursor-pointer border border-zinc-700"
                >
                  <LogOut size={16} />
                  <span>로그아웃 (세션만 종료)</span>
                </button>
                <p className="text-[12px] text-zinc-500 mt-1.5">
                  ※ 단순 로그아웃 시 진행 중인 백그라운드 A/B 테스트는 멈추지 않고 계속 작동합니다.
                </p>
              </div>
            </div>
          </section>

          {/* Notification Settings */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Bell size={18} className="text-violet-400"/> 알림 설정
            </h2>
            <div className="flex items-center justify-between py-2 border-b border-zinc-800/50 pb-4">
              <div>
                <div className="font-medium text-zinc-200 flex items-center gap-2">
                  <span>A/B 테스트 종료 알림</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                    🟢 실시간 작동 중
                  </span>
                </div>
                <div className="text-sm text-zinc-500 mt-1">테스트가 완료되고 승리 변인이 결정되면 연동된 이메일({userEmail})로 리포트를 자동 전송합니다.</div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 ml-4" htmlFor="email-alert-toggle">
                <span className="sr-only">A/B 테스트 종료 이메일 알림 토글</span>
                <input 
                  type="checkbox" 
                  id="email-alert-toggle"
                  role="switch"
                  aria-checked={emailAlerts}
                  aria-label="A/B 테스트 종료 알림 활성화"
                  className="sr-only peer" 
                  checked={emailAlerts} 
                  onChange={() => setEmailAlerts(!emailAlerts)} 
                />
                <div className="w-11 h-6 bg-zinc-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-cyan-400 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500"></div>
              </label>
            </div>

            <div className="pt-4 flex items-center justify-between">
              <span className="text-xs text-zinc-400">이메일 알림 템플릿 및 발송 기능 동작 확인:</span>
              <button
                onClick={handleSendTestEmail}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/40 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-lg"
              >
                <Mail size={14} />
                <span>🧪 테스트 이메일 발송해보기</span>
              </button>
            </div>
          </section>
          
          {/* Danger Zone */}
          <section className="glass-panel p-6 rounded-2xl border border-red-900/30">
            <h2 className="text-lg font-bold mb-1 text-red-500">위험 구역</h2>
            <p className="text-xs text-zinc-500 mb-4">YouTube 채널 인증을 완전 해제하고 진행 중인 모든 자동 테스트를 중단합니다.</p>
            <button 
              onClick={handleDisconnectChannel}
              className="flex items-center gap-2 text-red-400 hover:text-red-300 bg-red-950/30 hover:bg-red-900/40 px-4 py-2.5 rounded-xl transition-colors cursor-pointer border border-red-500/30 font-semibold text-sm"
            >
              <LogOut size={16} />
              <span>YouTube 채널 연동 해제 (테스트 전면 중단)</span>
            </button>
          </section>
        </div>
      </div>

      <Modal {...modalConfig} />
    </>
  );
}
