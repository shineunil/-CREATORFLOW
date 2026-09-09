"use client";

import React, { useState, useRef } from "react";
import { Settings, Mail, Bell, Shield, LogOut, PlaySquare, Plus, AlertTriangle, CreditCard, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modal from "@/components/Modal";
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

export default function SettingsPage() {
  const router = useRouter();
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [userEmail, setUserEmail] = useState<string>("로딩 중...");
  const [isPro, setIsPro] = useState(false);
  const [plan, setPlan] = useState<string>("BASIC");
  const [isOpeningPortal, setIsOpeningPortal] = useState(false);
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [maxChannels, setMaxChannels] = useState(1);
  const [isSwitching, setIsSwitching] = useState(false);
  // state만으로 중복 클릭을 막으면 리렌더 반영 전 짧은 틈에 두 번째 클릭이 통과할 수 있어 ref로 보강한다.
  const isSwitchingRef = useRef(false);
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

  const loadAccountInfo = () => {
    apiFetch("/api/user/me")
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load profile (${res.status})`);
        return res.json();
      })
      .then((data) => {
        if (data.email) setUserEmail(data.email);
        else setUserEmail("연동된 채널 이메일 없음");
        setIsPro(!!data.is_pro);
        setPlan(data.plan || "BASIC");
      })
      .catch((err) => {
        console.error(err);
        setUserEmail("연동된 채널 이메일 없음");
      });

    apiFetch("/api/channels")
      .then((res) => res.json())
      .then((data) => {
        setChannels(data.channels || []);
        setMaxChannels(data.max_channels ?? 1);
      })
      .catch((err) => console.error(err));
  };

  React.useEffect(() => {
    loadAccountInfo();
    // 다른 곳(우측 상단 헤더, 다른 페이지의 좌측 상단 select box)에서 채널을 전환해도
    // 이 페이지에 표시되는 계정/채널 정보가 새로고침 없이 최신 상태로 갱신되도록 한다.
    window.addEventListener(CHANNEL_SWITCHED_EVENT, loadAccountInfo);
    return () => window.removeEventListener(CHANNEL_SWITCHED_EVENT, loadAccountInfo);
  }, []);

  const handleSwitchChannel = async (channelId: number) => {
    if (isSwitchingRef.current) return;
    isSwitchingRef.current = true;
    setIsSwitching(true);
    const ok = await switchChannel(channelId);
    if (!ok) showAlert("오류 발생", "채널 전환 중 오류가 발생했습니다.", "error");
    isSwitchingRef.current = false;
    setIsSwitching(false);
  };

  const handleConnectAnotherChannel = () => {
    // 지금 로그인된 유저의 JWT를 state로 실어 보내야, 콜백에서 새 채널을 (구글 로그인이
    // 다른 계정/브랜드 계정으로 이뤄지더라도) 지금 이 유저 소유로 붙일 수 있다.
    const currentToken = localStorage.getItem("jwt_token");
    const stateParam = currentToken ? `?state=${encodeURIComponent(currentToken)}` : "";
    window.location.href = `${API_BASE_URL}/api/auth/login${stateParam}`;
  };

  const handleOpenBillingPortal = async () => {
    if (isOpeningPortal) return;
    setIsOpeningPortal(true);
    try {
      const res = await apiFetch("/api/billing/portal");
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showAlert("결제 관리 페이지를 열 수 없습니다", err.detail || "잠시 후 다시 시도해주세요.", "error");
        return;
      }
      const data = await res.json();
      window.open(data.url, "_blank", "noopener,noreferrer");
    } catch (e) {
      console.error(e);
      showAlert("오류 발생", "결제 관리 페이지를 여는 중 오류가 발생했습니다.", "error");
    } finally {
      setIsOpeningPortal(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
      localStorage.removeItem("jwt_token");
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
      localStorage.removeItem("jwt_token");
      localStorage.removeItem("connectedChannel");
      window.location.href = "/";
    }
  };

  const handleDisconnectChannel = (channelId: number, channelTitle: string) => {
    showConfirm(
      "⚠️ YouTube 채널 연동 해제",
      `"${channelTitle || "이 채널"}" 연동을 해제하시겠습니까?\n이 채널에서 진행 중인 모든 A/B 테스트 순환 및 측정이 즉시 중단됩니다. 다른 연동 채널이나 계정 로그인에는 영향이 없습니다.`,
      async () => {
        try {
          const res = await apiFetch(`/api/channels/${channelId}/disconnect`, { method: "POST" });
          if (!res.ok) throw new Error("disconnect failed");
          // 로그아웃하지 않고 채널 목록만 새로고침한다 - 해제된 건 이 채널 하나뿐이고
          // 계정·다른 채널 연동은 그대로 유지되므로 세션을 끊을 이유가 없다.
          loadAccountInfo();
          showAlert("🔒 채널 연동 해제 완료", "YouTube 연동이 해제되었습니다. 다시 연동하려면 목록에서 재연동해주세요.", "success");
        } catch (e) {
          console.error(e);
          showAlert("오류 발생", "채널 연동 해제 중 오류가 발생했습니다.", "error");
        }
      },
      "error"
    );
  };

  const handleSendTestEmail = async () => {
    try {
      const res = await apiFetch("/api/settings/test-email", { method: "POST" });
      const data = await res.json();
      if (data.simulated) {
        showAlert("📧 시뮬레이션 모드 (실제 미발송)", data.message, "warning");
      } else if (data.status === "ok") {
        showAlert("📧 이메일 발송 완료", data.message, "success");
      } else {
        showAlert("오류 발생", data.message || "이메일 알림 발송 중 오류가 발생했습니다.", "error");
      }
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
            <Settings className="text-zinc-400" aria-hidden="true" /> 설정
          </h1>
          <p className="text-zinc-400 mt-2">계정 및 알림 환경을 설정합니다.</p>
        </div>

        <div className="space-y-6">
          {/* Account Settings */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Shield size={18} className="text-cyan-400" aria-hidden="true" /> 계정 정보
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">연동된 구글 이메일</label>
                <input type="text" disabled value={userEmail} className="w-full bg-zinc-900/50 border border-zinc-800 text-cyan-400 font-semibold rounded-lg p-3 text-sm cursor-not-allowed" />
              </div>
              <div className="pt-2">
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-semibold rounded-xl transition-colors cursor-pointer border border-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                >
                  <LogOut size={16} aria-hidden="true" />
                  <span>로그아웃 (세션만 종료)</span>
                </button>
                <p className="text-[12px] text-zinc-400 mt-1.5">
                  ※ 단순 로그아웃 시 진행 중인 백그라운드 A/B 테스트는 멈추지 않고 계속 작동합니다.
                </p>
              </div>
            </div>
          </section>

          {/* Connected Channels */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
              <PlaySquare size={18} className="text-cyan-400" aria-hidden="true" /> 연동된 채널 ({channels.length}/{maxChannels})
            </h2>
            <p className="text-xs text-zinc-400 mb-4">한 계정으로 여러 YouTube 채널을 연동하고 전환할 수 있습니다. PRO/AGENCY 요금제는 더 많은 채널을 연동할 수 있습니다.</p>
            <div className="space-y-2">
              {channels.map((c) => (
                <div key={c.id} className={`flex items-center gap-3 p-3 rounded-xl border ${c.is_active ? "bg-cyan-500/5 border-cyan-500/30" : "bg-zinc-900/40 border-zinc-800"}`}>
                  <div className="w-9 h-9 rounded-full bg-zinc-800 flex items-center justify-center text-sm font-bold text-zinc-300 flex-shrink-0" aria-hidden="true">
                    {c.channel_title ? c.channel_title.substring(0, 1).toUpperCase() : "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold text-white truncate">{c.channel_title || "이름 없음"}</div>
                    {!c.is_connected ? (
                      <div className="text-xs text-zinc-500">연동 해제됨 · "다른 채널 연동하기"로 다시 연동 가능</div>
                    ) : c.needs_reconnect ? (
                      <div className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle size={11} aria-hidden="true" /> 재연동 필요</div>
                    ) : null}
                  </div>
                  {c.is_active && (
                    <span className="text-xs font-bold text-cyan-400 px-2.5 py-1">사용 중</span>
                  )}
                  {!c.is_active && c.is_connected && (
                    <button
                      onClick={() => handleSwitchChannel(c.id)}
                      disabled={isSwitching}
                      className="text-xs font-bold text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 rounded-lg transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                    >
                      전환
                    </button>
                  )}
                  {c.is_connected && (
                    <button
                      onClick={() => handleDisconnectChannel(c.id, c.channel_title)}
                      title="이 채널 연동 해제"
                      aria-label={`${c.channel_title || "이 채널"} 연동 해제`}
                      className="p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-950/30 rounded-lg transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                    >
                      <LogOut size={15} aria-hidden="true" />
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              onClick={handleConnectAnotherChannel}
              disabled={channels.length >= maxChannels}
              className="mt-3 flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-semibold rounded-xl transition-colors cursor-pointer border border-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              title={channels.length >= maxChannels ? "요금제의 채널 연동 한도에 도달했습니다" : ""}
            >
              <Plus size={16} aria-hidden="true" />
              <span>{channels.length >= maxChannels ? "채널 한도 도달 (업그레이드 필요)" : "다른 채널 연동하기"}</span>
            </button>
          </section>

          {/* Billing */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
              <CreditCard size={18} className="text-cyan-400" aria-hidden="true" /> 결제 관리
            </h2>
            <p className="text-xs text-zinc-400 mb-4">
              현재 요금제: <span className="font-bold text-zinc-200">{plan}</span>
              {isPro && " — 구독 취소, 결제수단 변경, 결제 내역/영수증 조회는 Paddle의 결제 관리 페이지에서 처리합니다."}
            </p>
            {isPro ? (
              <button
                onClick={handleOpenBillingPortal}
                disabled={isOpeningPortal}
                className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-semibold rounded-xl transition-colors cursor-pointer border border-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                {isOpeningPortal ? (
                  <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                ) : (
                  <CreditCard size={16} aria-hidden="true" />
                )}
                <span>구독 취소 / 결제 내역 관리 (Paddle)</span>
              </button>
            ) : (
              <Link
                href="/pricing"
                className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-sm font-semibold rounded-xl transition-colors border border-cyan-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <CreditCard size={16} aria-hidden="true" />
                <span>PRO로 업그레이드</span>
              </Link>
            )}
          </section>

          {/* Notification Settings */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Bell size={18} className="text-violet-400" aria-hidden="true" /> 알림 설정
            </h2>
            <div className="flex items-center justify-between py-2 border-b border-zinc-800/50 pb-4">
              <div>
                <div className="font-medium text-zinc-200 flex items-center gap-2">
                  <span>A/B 테스트 종료 알림</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                    🟢 실시간 작동 중
                  </span>
                </div>
                <div className="text-sm text-zinc-400 mt-1">테스트가 완료되고 승리 변인이 결정되면 연동된 이메일({userEmail})로 리포트를 자동 전송합니다.</div>
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
                className="flex items-center gap-1.5 px-3.5 py-2 bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/40 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <Mail size={14} aria-hidden="true" />
                <span>🧪 테스트 이메일 발송해보기</span>
              </button>
            </div>
          </section>
        </div>
      </div>

      <Modal {...modalConfig} />
    </>
  );
}
