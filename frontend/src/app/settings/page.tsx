"use client";

import React, { useState, useRef } from "react";
import { Settings, Mail, Bell, Shield, LogOut, PlaySquare, Plus, AlertTriangle, CreditCard, Loader2, CheckCircle2, Trash2, RefreshCw, Image, Type, ExternalLink, Languages } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Modal from "@/components/Modal";
import { apiFetch } from "@/lib/api";
import { API_BASE_URL } from "@/lib/config";
import { switchChannel, CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";
import { useI18n } from "@/i18n/I18nProvider";
import LanguageSwitcher from "@/components/LanguageSwitcher";

type ChannelSummary = {
  id: number;
  channel_title: string;
  youtube_channel_id: string;
  needs_reconnect: boolean;
  is_connected: boolean;
  is_active: boolean;
  thumbnail_permission: "unknown" | "allowed" | "denied";
};

export default function SettingsPage() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const S = t.settings;
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [userEmail, setUserEmail] = useState<string>(t.common.loading);
  const [isPro, setIsPro] = useState(false);
  const [plan, setPlan] = useState<string>("BASIC");

  // 알림 이메일 인증 상태
  const [notifEmail, setNotifEmail] = useState<string | null>(null);
  const [notifEmailVerified, setNotifEmailVerified] = useState(false);
  const [notifEmailInput, setNotifEmailInput] = useState("");
  const [notifCodeInput, setNotifCodeInput] = useState("");
  const [notifStep, setNotifStep] = useState<"idle" | "code_sent" | "done">("idle");
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifMsg, setNotifMsg] = useState<{ text: string; type: "ok" | "err" } | null>(null);
  const [isOpeningPortal, setIsOpeningPortal] = useState(false);
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [maxChannels, setMaxChannels] = useState(1);
  const [isSwitching, setIsSwitching] = useState(false);
  const [checkingCapabilities, setCheckingCapabilities] = useState<Record<number, boolean>>({});
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
        else setUserEmail(S.noEmail);
        setIsPro(!!data.is_pro);
        setPlan(data.plan || "BASIC");
        setNotifEmail(data.notification_email || null);
        setNotifEmailVerified(!!data.notification_email_verified);
        if (data.notification_email) setNotifEmailInput(data.notification_email);
        if (typeof data.email_alerts_enabled === "boolean") setEmailAlerts(data.email_alerts_enabled);
      })
      .catch((err) => {
        console.error(err);
        setUserEmail(S.noEmail);
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
    if (!ok) showAlert(t.common.error, S.switchError, "error");
    isSwitchingRef.current = false;
    setIsSwitching(false);
  };

  const handleConnectAnotherChannel = () => {
    // L-3: JWT를 URL에 노출할 필요 없음 — 백엔드가 HttpOnly 쿠키에서 현재 유저를 직접 읽음
    window.location.href = `${API_BASE_URL}/api/auth/login?locale=${locale}`;
  };

  const handleOpenBillingPortal = async () => {
    if (isOpeningPortal) return;
    setIsOpeningPortal(true);
    try {
      const res = await apiFetch("/api/billing/portal");
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showAlert(S.portalErrorTitle, err.detail || S.portalRetry, "error");
        return;
      }
      const data = await res.json();
      window.open(data.url, "_blank", "noopener,noreferrer");
    } catch (e) {
      console.error(e);
      showAlert(t.common.error, S.portalError, "error");
    } finally {
      setIsOpeningPortal(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
      localStorage.removeItem("isLoggedIn");
      localStorage.removeItem("connectedChannel");
      showAlert(
        S.loggedOutTitle,
        S.loggedOutMsg,
        "info",
        () => {
          window.location.href = "/";
        }
      );
    } catch (e) {
      console.error(e);
      localStorage.removeItem("isLoggedIn");
      localStorage.removeItem("connectedChannel");
      window.location.href = "/";
    }
  };

  const handleCheckCapabilities = async (channelId: number) => {
    setCheckingCapabilities(prev => ({ ...prev, [channelId]: true }));
    try {
      const res = await apiFetch(`/api/channels/${channelId}/check-capabilities`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setChannels(prev => prev.map(c => c.id === channelId ? { ...c, thumbnail_permission: data.thumbnail_permission } : c));
      } else {
        const msg = typeof data.detail === "string" ? data.detail
          : data.error ? String(data.error)
          : S.serverError(res.status);
        showAlert(t.common.error, msg, "error");
      }
    } catch {
      showAlert(t.common.error, S.genericError, "error");
    } finally {
      setCheckingCapabilities(prev => ({ ...prev, [channelId]: false }));
    }
  };

  const handleDisconnectChannel = (channelId: number, channelTitle: string) => {
    showConfirm(
      S.disconnectConfirmTitle,
      S.disconnectConfirmMsg(channelTitle || S.thisChannel),
      async () => {
        try {
          const res = await apiFetch(`/api/channels/${channelId}/disconnect`, { method: "POST" });
          if (!res.ok) throw new Error("disconnect failed");
          // 로그아웃하지 않고 채널 목록만 새로고침한다 - 해제된 건 이 채널 하나뿐이고
          // 계정·다른 채널 연동은 그대로 유지되므로 세션을 끊을 이유가 없다.
          loadAccountInfo();
          showAlert(S.disconnectedTitle, S.disconnectedMsg, "success");
        } catch (e) {
          console.error(e);
          showAlert(t.common.error, S.disconnectError, "error");
        }
      },
      "error"
    );
  };

  const handleSendVerifyCode = async () => {
    if (!notifEmailInput.trim() || !notifEmailInput.includes("@")) {
      setNotifMsg({ text: S.invalidEmail, type: "err" });
      return;
    }
    setNotifLoading(true);
    setNotifMsg(null);
    try {
      const res = await apiFetch("/api/user/notification-email/send-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: notifEmailInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setNotifStep("code_sent");
        setNotifMsg({ text: data.simulated ? S.codeSimulated : S.codeSent, type: "ok" });
      } else {
        setNotifMsg({ text: data.detail || S.sendFailed, type: "err" });
      }
    } catch {
      setNotifMsg({ text: S.sendError, type: "err" });
    } finally {
      setNotifLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!notifCodeInput.trim()) {
      setNotifMsg({ text: S.enterCode, type: "err" });
      return;
    }
    setNotifLoading(true);
    setNotifMsg(null);
    try {
      const res = await apiFetch("/api/user/notification-email/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: notifCodeInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setNotifEmail(data.notification_email);
        setNotifEmailVerified(true);
        setNotifStep("done");
        setNotifMsg({ text: S.verifiedMsg, type: "ok" });
        setNotifCodeInput("");
      } else {
        setNotifMsg({ text: data.detail || S.wrongCode, type: "err" });
      }
    } catch {
      setNotifMsg({ text: S.verifyError, type: "err" });
    } finally {
      setNotifLoading(false);
    }
  };

  const handleRemoveNotifEmail = async () => {
    setNotifLoading(true);
    setNotifMsg(null);
    try {
      await apiFetch("/api/user/notification-email", { method: "DELETE" });
      setNotifEmail(null);
      setNotifEmailVerified(false);
      setNotifEmailInput("");
      setNotifStep("idle");
      setNotifMsg({ text: S.removed, type: "ok" });
    } catch {
      setNotifMsg({ text: S.removeError, type: "err" });
    } finally {
      setNotifLoading(false);
    }
  };

  const handleSendTestEmail = async () => {
    try {
      const res = await apiFetch("/api/settings/test-email", { method: "POST" });
      const data = await res.json();
      if (data.simulated) {
        showAlert(S.simulationTitle, data.message, "warning");
      } else if (data.status === "ok") {
        showAlert(S.sentTitle, data.message, "success");
      } else {
        showAlert(t.common.error, data.message || S.testEmailError, "error");
      }
    } catch (e) {
      console.error(e);
      showAlert(t.common.error, S.testEmailError, "error");
    }
  };

  return (
    <>
      <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-zinc-800/20 rounded-full blur-[120px] -z-10 pointer-events-none" />
      <div className="max-w-7xl w-full mx-auto p-8 pb-20">
        <div className="mb-10">
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Settings className="text-zinc-400" aria-hidden="true" /> {S.title}
          </h1>
          <p className="text-zinc-400 mt-2">{S.sub}</p>
        </div>

        <div className="space-y-6">
          {/* Account Settings */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Shield size={18} className="text-cyan-400" aria-hidden="true" /> {S.account}
            </h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="account-email" className="block text-sm text-zinc-400 mb-1">{S.googleEmail}</label>
                <input id="account-email" type="text" disabled value={userEmail} className="w-full bg-zinc-900/50 border border-zinc-800 text-cyan-400 font-semibold rounded-lg p-3 text-sm cursor-not-allowed" />
              </div>
              <div className="pt-2">
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-semibold rounded-xl transition-colors cursor-pointer border border-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                >
                  <LogOut size={16} aria-hidden="true" />
                  <span>{S.logout}</span>
                </button>
                <p className="text-[12px] text-zinc-400 mt-1.5">
                  {S.logoutNote}
                </p>
              </div>
            </div>
          </section>

          {/* Language */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
              <Languages size={18} className="text-cyan-400" aria-hidden="true" /> {S.languageTitle}
            </h2>
            <p className="text-xs text-zinc-400 mb-4">{S.languageSub}</p>
            <LanguageSwitcher />
          </section>

          {/* Connected Channels */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
              <PlaySquare size={18} className="text-cyan-400" aria-hidden="true" /> {S.channelsTitle(channels.length, maxChannels)}
            </h2>
            <p className="text-xs text-zinc-400 mb-4">{S.channelsSub}</p>
            <div className="space-y-2">
              {channels.map((c) => (
                <div key={c.id} className={`flex items-center gap-3 p-3 rounded-xl border ${c.is_active ? "bg-cyan-500/5 border-cyan-500/30" : "bg-zinc-900/40 border-zinc-800"}`}>
                  <div className="w-9 h-9 rounded-full bg-zinc-800 flex items-center justify-center text-sm font-bold text-zinc-300 flex-shrink-0" aria-hidden="true">
                    {c.channel_title ? c.channel_title.substring(0, 1).toUpperCase() : "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold text-white truncate">{c.channel_title || t.common.untitled}</div>
                    {!c.is_connected ? (
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className="inline-flex text-[11px] font-bold text-zinc-300 bg-zinc-700/80 px-2 py-0.5 rounded-full">{S.disconnected}</span>
                        <span className="text-xs text-zinc-400">{S.reconnectBelow}</span>
                      </div>
                    ) : c.needs_reconnect ? (
                      <div className="text-xs text-amber-400 flex items-center gap-1"><AlertTriangle size={11} aria-hidden="true" /> {S.reconnectNeeded}</div>
                    ) : null}
                  </div>
                  {c.is_active && (
                    <span className="text-xs font-bold text-cyan-400 px-2.5 py-1 whitespace-nowrap">{S.active}</span>
                  )}
                  {!c.is_active && c.is_connected && (
                    <button
                      onClick={() => handleSwitchChannel(c.id)}
                      disabled={isSwitching}
                      className="text-xs font-bold text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 rounded-lg transition-colors cursor-pointer disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                    >
                      {S.switch}
                    </button>
                  )}
                  {c.is_connected && (
                    <button
                      onClick={() => handleDisconnectChannel(c.id, c.channel_title)}
                      title={S.disconnectTooltip}
                      aria-label={S.disconnectAria(c.channel_title || S.thisChannel)}
                      className="flex items-center gap-1.5 text-xs font-bold text-red-400/80 hover:text-red-300 bg-red-950/20 hover:bg-red-950/40 border border-red-500/20 hover:border-red-500/40 px-3 py-1.5 rounded-lg transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                    >
                      <LogOut size={14} aria-hidden="true" />
                      <span className="whitespace-nowrap">{S.disconnect}</span>
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              onClick={handleConnectAnotherChannel}
              disabled={channels.length >= maxChannels}
              className="mt-3 flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-semibold rounded-xl transition-colors cursor-pointer border border-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              title={channels.length >= maxChannels ? S.limitTooltip : ""}
            >
              <Plus size={16} aria-hidden="true" />
              <span>{channels.length >= maxChannels ? S.limitReached : S.connectAnother}</span>
            </button>
          </section>

          {/* Channel Capabilities */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
              <Shield size={18} className="text-cyan-400" aria-hidden="true" /> {S.capTitle}
            </h2>
            <p className="text-xs text-zinc-400 mb-4">
              {S.capSub}
            </p>
            <div className="space-y-4">
              {channels.filter(c => c.is_connected).map((c) => {
                const perm = c.thumbnail_permission || "unknown";
                const isChecking = !!checkingCapabilities[c.id];
                return (
                  <div key={c.id} className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-bold text-zinc-300 flex-shrink-0" aria-hidden="true">
                        {c.channel_title ? c.channel_title.substring(0, 1).toUpperCase() : "?"}
                      </div>
                      <span className="font-semibold text-sm text-white">{c.channel_title || t.common.untitled}</span>
                      {c.is_active && <span className="text-[11px] font-bold text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-full">{S.active}</span>}
                    </div>

                    <div className="space-y-2">
                      {/* 제목 변경 — 항상 가능 */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Type size={14} className="text-zinc-400" aria-hidden="true" />
                          <span className="text-sm text-zinc-300">{S.titleChange}</span>
                        </div>
                        <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full whitespace-nowrap">{S.available}</span>
                      </div>

                      {/* 맞춤 썸네일 */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Image size={14} className="text-zinc-400" aria-hidden="true" />
                          <span className="text-sm text-zinc-300">{S.customThumb}</span>
                        </div>
                        {perm === "allowed" ? (
                          <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full whitespace-nowrap">{S.verified}</span>
                        ) : perm === "denied" ? (
                          <span className="text-xs font-bold text-red-400 bg-red-500/10 border border-red-500/20 px-2.5 py-1 rounded-full whitespace-nowrap">{S.verificationRequired}</span>
                        ) : (
                          <span className="text-xs font-bold text-zinc-400 bg-zinc-800 border border-zinc-700 px-2.5 py-1 rounded-full whitespace-nowrap">{S.notChecked}</span>
                        )}
                      </div>
                    </div>

                    {perm === "denied" && (
                      <div className="mt-3 flex items-start gap-2 px-3 py-2.5 bg-amber-950/40 border border-amber-500/30 rounded-lg">
                        <AlertTriangle size={13} className="text-amber-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
                        <p className="text-xs text-amber-300 leading-relaxed">
                          {S.deniedBefore}
                          <a
                            href={`https://accounts.google.com/AccountChooser?Email=${encodeURIComponent(userEmail || "")}&continue=https%3A%2F%2Fwww.youtube.com%2Ffeatures`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 underline text-amber-200 hover:text-white font-semibold"
                          >
                            youtube.com/features <ExternalLink size={11} aria-hidden="true" />
                          </a>{S.deniedAfter}
                        </p>
                      </div>
                    )}

                    <button
                      onClick={() => handleCheckCapabilities(c.id)}
                      disabled={isChecking}
                      className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-zinc-400 hover:text-zinc-200 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                    >
                      {isChecking ? <Loader2 size={12} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={12} aria-hidden="true" />}
                      {isChecking ? S.checking : S.checkNow}
                    </button>
                  </div>
                );
              })}
              {channels.filter(c => c.is_connected).length === 0 && (
                <p className="text-sm text-zinc-400 py-2">{S.noChannels}</p>
              )}
            </div>
          </section>

          {/* Billing */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-1 flex items-center gap-2">
              <CreditCard size={18} className="text-cyan-400" aria-hidden="true" /> {S.billingTitle}
            </h2>
            <p className="text-xs text-zinc-400 mb-4">
              {S.currentPlan}<span className="font-bold text-zinc-200">{plan}</span>
              {isPro && S.portalNote}
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
                <span>{S.manageSub}</span>
              </button>
            ) : (
              <Link
                href="/pricing"
                className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-sm font-semibold rounded-xl transition-colors border border-cyan-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <CreditCard size={16} aria-hidden="true" />
                <span>{S.upgrade}</span>
              </Link>
            )}
          </section>

          {/* Notification Settings */}
          <section className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
            <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
              <Bell size={18} className="text-violet-400" aria-hidden="true" /> {S.notifTitle}
            </h2>

            {!isPro ? (
              <div className="flex flex-col items-start gap-3 py-4 px-5 rounded-xl bg-zinc-900/60 border border-zinc-700/50">
                <p className="text-sm text-zinc-400">
                  <span className="text-zinc-200 font-semibold">{S.proOnlyStrong}</span>{S.proOnlyMiddle}
                  <span className="text-cyan-400 font-bold">PRO</span>{S.proOnlyAfter}
                </p>
                <Link
                  href="/pricing"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-sm font-semibold rounded-xl transition-colors border border-cyan-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                >
                  <CreditCard size={15} aria-hidden="true" />
                  {S.upgrade}
                </Link>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50 pb-4">
                  <div>
                    <div className="font-medium text-zinc-200 flex items-center gap-2">
                      <span>{S.alertsTitle}</span>
                      <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                        {S.live}
                      </span>
                    </div>
                    <div className="text-sm text-zinc-400 mt-1">
                      {S.reportBefore}
                      <span className="text-cyan-400 font-medium">
                        {notifEmail && notifEmailVerified ? notifEmail : userEmail}
                      </span>
                      {notifEmail && notifEmailVerified && (
                        <span className="ml-1.5 text-[11px] px-1.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">{S.custom}</span>
                      )}
                      {S.reportAfter}
                    </div>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer flex-shrink-0 ml-4" htmlFor="email-alert-toggle">
                    <span className="sr-only">{S.toggleSr}</span>
                    <input
                      type="checkbox"
                      id="email-alert-toggle"
                      role="switch"
                      aria-checked={emailAlerts}
                      aria-label={S.toggleAria}
                      className="sr-only peer"
                      checked={emailAlerts}
                      onChange={async () => {
                        const next = !emailAlerts;
                        setEmailAlerts(next);
                        try {
                          await apiFetch("/api/user/preferences", {
                            method: "PATCH",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ email_alerts_enabled: next }),
                          });
                        } catch {
                          setEmailAlerts(!next); // 실패하면 롤백
                        }
                      }}
                    />
                    <div className="w-11 h-6 bg-zinc-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-cyan-400 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500"></div>
                  </label>
                </div>

                {/* 알림 수신 이메일 설정 */}
                <div className="pt-4 border-b border-zinc-800/50 pb-5">
                  <div className="font-medium text-zinc-200 mb-1 flex items-center gap-2">
                    <Mail size={14} className="text-cyan-400" aria-hidden="true" />
                    {S.notifEmailTitle}
                  </div>
                  <p className="text-xs text-zinc-400 mb-3">
                    {S.notifEmailSub}
                  </p>

                  {notifEmail && notifEmailVerified ? (
                    <div className="flex items-center gap-3 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3">
                      <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" aria-hidden="true" />
                      <span className="text-sm text-white flex-1 truncate">{notifEmail}</span>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex gap-2">
                        <input
                          type="email"
                          aria-label={S.notifEmailTitle}
                          value={notifEmailInput}
                          onChange={e => setNotifEmailInput(e.target.value)}
                          placeholder="your@gmail.com"
                          disabled={notifStep === "code_sent"}
                          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                        />
                        <button
                          onClick={handleSendVerifyCode}
                          disabled={notifLoading || notifStep === "code_sent"}
                          className="px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-bold transition-colors disabled:opacity-50 cursor-pointer whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                        >
                          {notifLoading && notifStep === "idle" ? <Loader2 size={14} className="animate-spin" /> : S.sendCode}
                        </button>
                      </div>

                      {notifStep === "code_sent" && (
                        <div className="flex gap-2">
                          <input
                            type="text"
                            inputMode="numeric"
                            aria-label={S.codePlaceholder}
                            value={notifCodeInput}
                            onChange={e => setNotifCodeInput(e.target.value.replace(/\D/g, "").slice(0, 6))}
                            placeholder={S.codePlaceholder}
                            maxLength={6}
                            className="flex-1 bg-zinc-900 border border-cyan-500/50 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-cyan-500 tracking-widest font-mono"
                          />
                          <button
                            onClick={handleVerifyCode}
                            disabled={notifLoading || notifCodeInput.length < 6}
                            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white text-sm font-bold transition-all disabled:opacity-50 cursor-pointer whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                          >
                            {notifLoading ? <Loader2 size={14} className="animate-spin" /> : S.verify}
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {notifMsg && (
                    <p className={`text-xs mt-2 font-medium ${notifMsg.type === "ok" ? "text-emerald-400" : "text-red-400"}`}>
                      {notifMsg.text}
                    </p>
                  )}
                </div>

              </>
            )}
          </section>
        </div>
      </div>

      <Modal {...modalConfig} />
    </>
  );
}
