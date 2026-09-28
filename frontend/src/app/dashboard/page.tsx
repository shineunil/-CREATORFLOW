"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  CheckCircle2,
  Sparkles,
  FlaskConical,
  Settings2,
  Trash2,
  Loader2,
  AlertTriangle
} from "lucide-react";
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  Cell,
} from "recharts";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import Modal from "@/components/Modal";
import ChannelSelect from "@/components/layout/ChannelSelect";
import { apiFetch } from "@/lib/api";
import { CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";
import { useI18n } from "@/i18n/I18nProvider";
import RichText from "@/i18n/RichText";
import { formatDate, parseServerDate } from "@/i18n/format";
import type { Dictionary } from "@/i18n/dictionaries";
import type { Locale } from "@/i18n/config";

const formatLocalDateTime = (iso: string | null | undefined): string => {
  if (!iso) return "-";
  try {
    const d = parseServerDate(iso);
    if (isNaN(d.getTime())) return iso;
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const min = String(d.getMinutes()).padStart(2, "0");
    return `${mm}-${dd} ${hh}:${min}`;
  } catch {
    return iso;
  }
};

const formatTestDuration = (startIso: string | null | undefined, endIso: string | null | undefined, status: string, t: Dictionary, locale: Locale) => {
  if (!startIso) return t.dashboard.notStarted;
  const start = parseServerDate(startIso);
  // 사용자가 끝낸 테스트(STOPPED)와 기간이 끝나 승자가 정해진 테스트(COMPLETED)는 남은 시간 대신 종료로 표시
  if (status === "STOPPED" || status === "COMPLETED") {
    return t.dashboard.finishedStarted(formatDate(start, locale));
  }
  const end = endIso ? parseServerDate(endIso) : new Date(start.getTime() + 24 * 60 * 60 * 1000);
  const now = new Date();
  const diffHours = Math.max(0, Math.floor((end.getTime() - now.getTime()) / (1000 * 60 * 60)));
  return t.dashboard.runningEnds(diffHours);
};

export default function Dashboard() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const D = t.dashboard;
  const searchParams = useSearchParams();
  const [testData, setTestData] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSwapping, setIsSwapping] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<any>({});
  // 여러 테스트를 연달아 빠르게 "즉시 교체"하면 각자 독립적으로 전체 목록을 새로고침하는데,
  // 네트워크 응답 순서가 요청 순서와 다르게 도착하면 이전(더 느린) 새로고침이 최신 상태를 덮어쓸 수
  // 있다. 매번 새로고침 시도에 번호를 매겨, 가장 최근 시도의 응답만 화면에 반영한다.
  const testsRefreshTokenRef = useRef(0);

  // Modal State
  const [modalConfig, setModalConfig] = useState<{
    isOpen: boolean;
    type?: "alert" | "confirm" | "loading";
    variant?: "info" | "success" | "warning" | "error";
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    onConfirm: () => void;
    onCancel?: () => void;
  }>({
    isOpen: false,
    title: "",
    message: "",
    onConfirm: () => {},
  });

  const showAlert = (title: string, message: string, variant: "info" | "success" | "warning" | "error" = "info", confirmText?: string) => {
    setModalConfig({
      isOpen: true,
      type: "alert",
      variant,
      title,
      message,
      ...(confirmText ? { confirmText } : {}),
      onConfirm: () => setModalConfig(prev => ({ ...prev, isOpen: false }))
    });
  };

  useEffect(() => {
    const errorFromUrl = searchParams.get("error");
    const upgradedFromUrl = searchParams.get("upgraded");

    if (errorFromUrl === "channel_limit_reached") {
      showAlert(D.channelLimitTitle, D.channelLimitMsg, "warning");
      router.replace("/dashboard");
    }

    // token/connected_channel URL 파라미터는 ClientLayout.tsx의 전역 useEffect가 이 페이지가
    // 마운트되기 전에 이미 localStorage에 저장하고 URL에서 제거한다. 여기서 다시 읽어서 처리하던
    // 예전 코드는 완전히 중복이었고(ClientLayout이 raw window.history.replaceState로 URL을 바꿔도
    // Next의 useSearchParams는 갱신되지 않아 이 페이지가 그 뒤에도 계속 예전 값을 보고 재실행됨),
    // connectedChannel 상태값도 실제로는 화면 어디에도 쓰이지 않아 제거했다.

    if (upgradedFromUrl === "true") {
      // 결제 웹훅이 비동기로 처리되어서, 결제 직후 바로 조회하면 아직 PRO로 안 바뀐 상태일 수
      // 있다. 몇 초 간격으로 최대 5번 재시도해서, 웹훅이 늦게 처리돼도 화면이 정확히 반영되게 한다.
      router.replace("/dashboard");
      let attempts = 0;
      const pollForPro = () => {
        apiFetch("/api/user/me")
          .then(res => res.json())
          .then(data => {
            setUserProfile(data);
            attempts += 1;
            if (data.is_pro) {
              showAlert(D.welcomeProTitle, D.welcomeProMsg, "success", t.common.ok);
            } else if (attempts < 5) {
              setTimeout(pollForPro, 2000);
            }
          })
          .catch(err => console.error(err));
      };
      pollForPro();
    } else {
      apiFetch("/api/user/me")
        .then(res => res.json())
        .then(data => setUserProfile(data))
        .catch(err => console.error(err));
    }

    apiFetch("/api/tests")
      .then(res => res.json())
      .then(data => {
        setTestData(data.tests || []);
        setIsLoading(false);
      })
      .catch(err => {
        console.error(err);
        setIsLoading(false);
      });
  }, [searchParams, router]);

  // 좌측 상단 select box(또는 우측 상단 헤더)에서 다른 채널로 전환하면, 새로고침 없이 그
  // 채널 기준 데이터로 다시 불러온다.
  useEffect(() => {
    const handleChannelSwitched = () => {
      setIsLoading(true);
      apiFetch("/api/user/me")
        .then(res => res.json())
        .then(data => setUserProfile(data))
        .catch(err => console.error(err));

      apiFetch("/api/tests")
        .then(res => res.json())
        .then(data => {
          setTestData(data.tests || []);
          setIsLoading(false);
        })
        .catch(err => {
          console.error(err);
          setIsLoading(false);
        });
    };
    window.addEventListener(CHANNEL_SWITCHED_EVENT, handleChannelSwitched);
    return () => window.removeEventListener(CHANNEL_SWITCHED_EVENT, handleChannelSwitched);
  }, []);

  const handleDeleteTest = (testId: string) => {
    const isBasic = !userProfile.is_pro;
    setModalConfig({
      isOpen: true,
      type: "confirm",
      variant: "error",
      title: D.deleteTitle,
      message: `${D.deleteMsg}${isBasic ? D.deleteBasicNote : ""}`,
      confirmText: D.deleteConfirm,
      cancelText: t.common.cancel,
      onConfirm: async () => {
        setModalConfig(prev => ({
          ...prev,
          type: "loading",
          title: D.deletingTitle,
          message: D.deletingMsg
        }));

        try {
          const res = await apiFetch(`/api/tests/${testId}`, { method: "DELETE" });
          if (res.ok) {
            showAlert(D.deletedTitle, D.deletedMsg, "success");
            setTestData(prevData => prevData.filter(test => test.test_id !== testId));
          } else {
            showAlert(t.common.error, D.deleteError, "error");
          }
        } catch(e) {
          showAlert(t.common.error, t.common.networkError, "error");
        }
      },
      onCancel: () => setModalConfig(prev => ({ ...prev, isOpen: false }))
    });
  };

  const handleStopTest = (testId: string) => {
    setModalConfig({
      isOpen: true,
      type: "confirm",
      variant: "warning",
      title: D.stopTitle,
      message: D.stopMsg,
      confirmText: D.stopConfirm,
      cancelText: t.common.cancel,
      onConfirm: async () => {
        setModalConfig(prev => ({
          ...prev,
          type: "loading",
          title: D.stoppingTitle,
          message: D.stoppingMsg
        }));
        try {
          const res = await apiFetch(`/api/tests/${testId}/stop`, { method: "POST" });
          if (res.ok) {
            showAlert(D.successTitle, D.stoppedMsg, "success");
            setTestData(prevData => prevData.map(test => test.test_id === testId ? { ...test, status: "STOPPED" } : test));
          } else {
            showAlert(t.common.error, D.stopError, "error");
          }
        } catch(e) {
          showAlert(t.common.error, t.common.networkError, "error");
        }
      },
      onCancel: () => setModalConfig(prev => ({ ...prev, isOpen: false }))
    });
  };

  const handleSwapTest = async (testId: string) => {
    setIsSwapping(testId);
    try {
      const res = await apiFetch(`/api/tests/${testId}/swap`, { method: "POST" });
      if (res.ok) {
        showAlert(D.swapSuccessTitle, D.swapSuccessMsg, "success");
        const myToken = ++testsRefreshTokenRef.current;
        apiFetch("/api/tests").then(r => r.json()).then(d => {
          if (testsRefreshTokenRef.current !== myToken) return;
          setTestData(d.tests || []);
        });
      } else if (res.status === 502) {
        const errData = await res.json().catch(() => ({}));
        // 전화번호 인증 안내 메시지에만 youtube.com/features 가 들어 있다 (영어·한국어 공통)
        const isPermission = (errData.detail || "").includes("youtube.com/features");
        showAlert(
          D.swapFailTitle,
          isPermission ? D.swapPermissionMsg : (errData.detail || D.swapRetryMsg),
          "warning"
        );
      } else {
        showAlert(D.swapFailedTitle, D.swapFailedMsg, "error");
      }
    } catch(e) {
      showAlert(t.common.error, D.commError, "error");
    } finally {
      setIsSwapping(null);
    }
  };

  return (
    <>
      <div className="px-8 pt-8 pb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tight">{D.title}</h1>
          <p className="text-sm text-zinc-400 mt-2">
            <RichText value={D.runningCount(testData.filter(test => test.status === "RUNNING").length)} strongClassName="text-cyan-400 font-semibold" />
          </p>
        </div>
        <ChannelSelect />
      </div>

      {userProfile.needs_reconnect && (
        <div className="mx-8 mb-2 flex flex-wrap items-center gap-3 justify-between px-5 py-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200">
          <div className="flex items-center gap-3">
            <AlertTriangle size={20} className="text-amber-400 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm">
              {D.reconnectMsg}
            </p>
          </div>
          <Link href="/login" className="px-4 py-2 bg-amber-500 text-black text-sm font-bold rounded-lg hover:bg-amber-400 transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            {D.reconnectBtn}
          </Link>
        </div>
      )}

      {userProfile.is_pro && userProfile.email?.includes("@pages.plusgoogle.com") && !userProfile.notification_email && (
        <div className="mx-8 mb-2 flex flex-wrap items-center gap-3 justify-between px-5 py-4 rounded-2xl bg-blue-500/10 border border-blue-500/30 text-blue-200">
          <div className="flex items-center gap-3">
            <AlertTriangle size={20} className="text-blue-400 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm">
              {D.brandMsg}
            </p>
          </div>
          <Link href="/settings" className="px-4 py-2 bg-blue-500 text-white text-sm font-bold rounded-lg hover:bg-blue-400 transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            {D.brandBtn}
          </Link>
        </div>
      )}

      <div className="p-8 w-full space-y-6">
        {isLoading ? (
          <div className="text-zinc-400 text-center py-20 animate-pulse" role="status">{D.loading}</div>
        ) : testData.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 text-center bg-zinc-900/30 rounded-3xl border border-zinc-800/50 border-dashed">
            <div className="w-20 h-20 bg-zinc-800/50 rounded-full flex items-center justify-center mb-6" aria-hidden="true">
              <FlaskConical size={32} className="text-zinc-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">{D.emptyTitle}</h2>
            <p className="text-zinc-400 mb-8 max-w-md">{D.emptySub}</p>
            <Link href="/new" className="px-6 py-3 bg-white text-black font-bold rounded-xl hover:bg-zinc-200 transition-colors flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              <Sparkles size={18} aria-hidden="true" /> {D.createNew}
            </Link>
          </div>
        ) : (
          testData.map((test: any) => (
            <div key={test.test_id} className="relative z-10 animate-fade-in-up">
              <div className="glass-panel rounded-2xl p-6 flex flex-wrap gap-8 justify-between items-end border border-zinc-800/50 mb-6 bg-zinc-900/40">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    {test.status === "RUNNING" ? (
                      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 text-xs font-bold border border-cyan-500/20">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" aria-hidden="true" /> {D.running}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-bold border border-emerald-500/20">
                        <CheckCircle2 size={12} aria-hidden="true" /> {D.finishedBadge}
                      </span>
                    )}
                  </div>
                  <h2 className="text-2xl font-bold mb-1 line-clamp-1">{test.video?.title || test.youtube_video_id}</h2>
                  <p className="text-sm text-zinc-400">{formatTestDuration(test.start_time, test.end_time, test.status, t, locale)}</p>
                </div>

                <div className="flex gap-10 text-right">
                  <Stat label={D.extraViews} value={D.viewsValue(test.variations.length > 0 ? Math.max(...test.variations.map((v: any) => v.total_views_gained || 0)) : 0)} highlight />
                  <Stat label={D.totalCandidates} value={`${test.variations.length}`} />
                </div>

                {test.status === "RUNNING" && (
                  <div className="w-full flex flex-col gap-3 pt-4 border-t border-zinc-800/50 mt-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSwapTest(test.test_id)}
                        disabled={isSwapping === test.test_id || test.manual_swap_used}
                        title={test.manual_swap_used ? D.swapUsedTooltip : undefined}
                        className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded-lg text-sm font-bold transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                      >
                        {isSwapping === test.test_id ? (
                          <>
                            <Loader2 size={16} className="animate-spin" aria-hidden="true" /> {D.swapping}
                          </>
                        ) : test.manual_swap_used ? (
                          <>
                            <Settings2 size={16} aria-hidden="true" /> {D.swapUsed}
                          </>
                        ) : (
                          <>
                            <Settings2 size={16} aria-hidden="true" /> {D.swapNow}
                          </>
                        )}
                      </button>
                      <button onClick={() => handleStopTest(test.test_id)} className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg text-sm font-bold transition-colors cursor-pointer flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                        <CheckCircle2 size={16} aria-hidden="true" /> {D.lockWinner}
                      </button>
                      <button onClick={() => handleDeleteTest(test.test_id)} className="ml-auto px-4 py-2 bg-zinc-700/50 hover:bg-red-900/40 text-zinc-200 hover:text-red-400 border border-zinc-500/50 hover:border-red-500/50 rounded-lg text-sm font-black transition-all cursor-pointer flex items-center gap-2 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400" title={D.deleteBtnTooltip}>
                        <Trash2 size={16} aria-hidden="true" /> {D.deleteBtn}
                      </button>
                    </div>
                    <div className="bg-zinc-800/30 rounded-lg p-3 text-xs text-zinc-400 leading-relaxed border border-zinc-800/50 space-y-1.5">
                      <p><strong className="text-zinc-300">{D.helpSwapStrong}</strong>{D.helpSwapText}</p>
                      <p><strong className="text-zinc-300">{D.helpLockStrong}</strong>{D.helpLockText}<span className="text-red-400 font-semibold">{D.helpLockWarn}</span></p>
                    </div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {test.variations.map((v: any, index: number) => (
                  <VariationCard
                    key={v.id}
                    title={v.name}
                    videoTitle={v.title_text}
                    viewsGained={`+${v.total_views_gained || 0}`}
                    views={t.common.views(String(v.total_views_gained || 0))}
                    data={v.chart_data || [{day: "Day 1", views_gained: 0}]}
                    color={index === 0 ? "#a1a1aa" : (v.is_winner ? "#06b6d4" : "#8b5cf6")}
                    isWinner={v.is_winner}
                    thumbnailUrl={v.thumbnail_image_url}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      <Modal {...modalConfig} />
    </>
  );
}

function Stat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-zinc-400 font-semibold uppercase tracking-wider mb-1">{label}</span>
      <span className={`text-3xl font-bold ${highlight ? "text-cyan-400" : "text-zinc-100"}`}>
        {value}
      </span>
    </div>
  );
}

function VariationCard({ title, videoTitle, viewsGained, views, data, color, isWinner, thumbnailUrl }: any) {
  const { t } = useI18n();
  const D = t.dashboard;
  return (
    <div className={`relative glass-panel rounded-2xl p-5 flex flex-col transition-all duration-300 border ${isWinner ? "winner-glow transform -translate-y-1 border-cyan-500/50" : "border-zinc-800"}`}>
      {isWinner && (
        <div className="absolute -top-3 -right-2 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-bold px-3 py-1 rounded-full shadow-lg shadow-cyan-500/20 flex items-center gap-1 border border-cyan-400/50 z-20">
          <CheckCircle2 size={16} aria-hidden="true" /> {D.winner}
        </div>
      )}
      
      <div className="flex justify-between items-center mb-4 relative">
        <span className={`text-sm font-medium ${isWinner ? "text-cyan-400" : "text-zinc-300"}`}>{title}</span>
        
        </div>

      <div className="w-full aspect-video bg-zinc-800 rounded-lg mb-4 border border-zinc-700/50 flex items-center justify-center relative overflow-hidden group">
         {thumbnailUrl && thumbnailUrl.startsWith("http") ? (
           <img src={thumbnailUrl} alt={D.thumbnailAlt(title)} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
         ) : (
           <>
             <div className="absolute inset-0 bg-gradient-to-tr from-zinc-800 to-zinc-700 group-hover:scale-105 transition-transform duration-500" />
             <span className="relative z-10 text-zinc-400 font-medium">{t.common.noImage}</span>
           </>
         )}
      </div>

      <div className="flex items-start justify-between gap-2 mb-6">
        <h3 className="text-sm font-semibold leading-tight line-clamp-2 text-zinc-100">{videoTitle}</h3>
      </div>

      <div className="mt-auto">
        <div className="flex justify-between items-end mb-2">
          <span className="text-sm text-zinc-400 uppercase font-medium tracking-wide">{D.viewsGained}</span>
          <span className={`text-xl font-bold ${isWinner ? "text-cyan-400" : "text-zinc-200"}`}>{viewsGained}</span>
        </div>
        <div className="h-24 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <Bar dataKey="views_gained" radius={[2, 2, 0, 0]}>
                {data.map((entry: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={entry.views_gained > 0 ? color : "#3f3f46"} className="transition-all duration-300 hover:opacity-80" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        <div className="flex justify-between items-center mt-4 pt-4 border-t border-zinc-800/50">
           <div className="flex flex-col gap-1">
              <span className="text-sm text-zinc-400 uppercase font-medium">{D.startedAt}</span>
              <span className="text-lg font-bold text-zinc-100">{formatLocalDateTime(data[0]?.day)}</span>
           </div>
           <div className="flex flex-col gap-1 text-right">
              <span className="text-sm text-zinc-400 uppercase font-medium">{D.totalViews}</span>
              <span className="text-lg font-bold text-zinc-100">{views}</span>
           </div>
        </div>
      </div>
    </div>
  );
}
