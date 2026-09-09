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

const formatTestDuration = (startIso: string | null | undefined, endIso: string | null | undefined, status: string) => {
  if (!startIso) return "Not started";
  if (startIso && !startIso.endsWith('Z')) startIso += 'Z';
  const start = new Date(startIso);
  if (status === "STOPPED") {
    return `완료된 최적화 (Started: ${start.toLocaleDateString()})`;
  }
  let end = endIso ? new Date(endIso.endsWith('Z') ? endIso : endIso + 'Z') : new Date(start.getTime() + 24 * 60 * 60 * 1000);
  const now = new Date();
  const diffHours = Math.max(0, Math.floor((end.getTime() - now.getTime()) / (1000 * 60 * 60)));
  return `최적화 진행 중 • ${diffHours}시간 후 종료 및 영구 적용`;
};

export default function Dashboard() {
  const router = useRouter();
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
      showAlert(
        "채널 연동 한도 도달",
        "현재 요금제에서 연동 가능한 채널 개수를 모두 사용했습니다. 더 많은 채널을 연동하려면 PRO/AGENCY로 업그레이드해주세요.",
        "warning"
      );
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
              showAlert("Welcome to PRO!", "Your account has been upgraded to PRO. Enjoy unlimited active tests and faster swap intervals.", "success", "OK");
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
    setModalConfig({
      isOpen: true,
      type: "confirm",
      variant: "error",
      title: "Cancel & Delete Test",
      message: "진행 중인 테스트를 완전히 Cancel하고 삭제하시겠습니까?\n유튜브 영상의 Thumbnail은 안전하게 '원본(A)'으로 자동 복구되며 삭제된 테스트는 복구할 수 없습니다.",
      confirmText: "네, 완전히 삭제합니다",
      cancelText: "Cancel",
      onConfirm: async () => {
        setModalConfig(prev => ({ 
          ...prev, 
          type: "loading", 
          title: "Deleting....", 
          message: "유튜브 Thumbnail을 안전하게 원본으로 복구하고 테스트를 삭제 중입니다.\n잠시만 기다려주세요..." 
        }));
        
        try {
          const res = await apiFetch(`/api/tests/${testId}`, { method: "DELETE" });
          if (res.ok) {
            showAlert("Deleted", "테스트가 완전히 Cancel되고 원본 Thumbnail로 복구되었습니다.", "success");
            setTestData(prevData => prevData.filter(t => t.test_id !== testId));
          } else {
            showAlert("Error", "An error occurred while deleting.", "error");
          }
        } catch(e) {
          showAlert("Error", "네트워크 Error가 발생했습니다.", "error");
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
      title: "End Test Early",
      message: "Currently까지 가장 높은 성과를 보인 Thumbnail로 영구 적용하고 최적화를 종료하시겠습니까?",
      confirmText: "Apply Now",
      cancelText: "Cancel",
      onConfirm: async () => {
        setModalConfig(prev => ({ 
          ...prev, 
          type: "loading", 
          title: "Ending Test....", 
          message: "유튜브 Thumbnail을 최종 승자로 확정하고 있습니다.\n잠시만 기다려주세요..." 
        }));
        try {
          const res = await apiFetch(`/api/tests/${testId}/stop`, { method: "POST" });
          if (res.ok) {
            showAlert("Success", "테스트가 Success적으로 종료되었으며, 최고 효율의 Thumbnail이 유튜브에 반영되었습니다.", "success");
            setTestData(prevData => prevData.map(t => t.test_id === testId ? { ...t, status: "STOPPED" } : t));
          } else {
            showAlert("Error", "An error occurred while ending the test.", "error");
          }
        } catch(e) {
          showAlert("Error", "네트워크 Error가 발생했습니다.", "error");
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
        showAlert("수동 교체 Success", "Thumbnail swapped successfully.", "success");
        const myToken = ++testsRefreshTokenRef.current;
        apiFetch("/api/tests").then(r => r.json()).then(d => {
          if (testsRefreshTokenRef.current !== myToken) return; // 더 최신 새로고침이 이미 진행됨 - 이 응답은 버림
          setTestData(d.tests || []);
        });
      } else {
        showAlert("Swap Failed", "수동 교체에 실패했습니다.", "error");
      }
    } catch(e) {
      showAlert("Error", "A communication error occurred.", "error");
    } finally {
      setIsSwapping(null);
    }
  };

  return (
    <>
      <div className="px-8 pt-8 pb-4">
        <div className="mb-4">
          <ChannelSelect />
        </div>
        <div>
          <h1 className="text-3xl font-black text-white tracking-tight">Optimization Dashboard</h1>
          <p className="text-sm text-zinc-400 mt-2">
            Currently <span className="text-cyan-400 font-semibold">{testData.filter(t => t.status === "RUNNING").length}</span> videos are being optimized.
          </p>
        </div>
      </div>

      {userProfile.needs_reconnect && (
        <div className="mx-8 mb-2 flex flex-wrap items-center gap-3 justify-between px-5 py-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200">
          <div className="flex items-center gap-3">
            <AlertTriangle size={20} className="text-amber-400 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm">
              YouTube 채널 연동이 만료되어 자동 A/B 테스트가 일시 중지되었습니다. 다시 로그인해서 재연동해주세요.
            </p>
          </div>
          <Link href="/login" className="px-4 py-2 bg-amber-500 text-black text-sm font-bold rounded-lg hover:bg-amber-400 transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
            채널 재연동하기
          </Link>
        </div>
      )}

      <div className="p-8 w-full space-y-6">
        {isLoading ? (
          <div className="text-zinc-400 text-center py-20 animate-pulse" role="status">Loading data...</div>
        ) : testData.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 text-center bg-zinc-900/30 rounded-3xl border border-zinc-800/50 border-dashed">
            <div className="w-20 h-20 bg-zinc-800/50 rounded-full flex items-center justify-center mb-6" aria-hidden="true">
              <FlaskConical size={32} className="text-zinc-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">No active optimizations</h2>
            <p className="text-zinc-400 mb-8 max-w-md">새로운 영상의 Thumbnail A/B 테스트를 만들어 조 views수를 극대화 해보세요.</p>
            <Link href="/new" className="px-6 py-3 bg-white text-black font-bold rounded-xl hover:bg-zinc-200 transition-colors flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
              <Sparkles size={18} aria-hidden="true" /> Create New Test
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
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" aria-hidden="true" /> Running
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-bold border border-emerald-500/20">
                        <CheckCircle2 size={12} aria-hidden="true" /> Optimization Finished
                      </span>
                    )}
                  </div>
                  <h2 className="text-2xl font-bold mb-1 line-clamp-1">{test.video?.title || test.youtube_video_id}</h2>
                  <p className="text-sm text-zinc-400">{formatTestDuration(test.start_time, test.end_time, test.status)}</p>
                </div>
                
                <div className="flex gap-10 text-right">
                  <Stat label="Extra Views Gained" value={`+${test.variations.length > 0 ? Math.max(...test.variations.map((v: any) => v.total_views_gained || 0)) : 0}  views`} highlight />
                  <Stat label="Total Candidates" value={`${test.variations.length}`} />
                </div>

                {test.status === "RUNNING" && (
                  <div className="w-full flex flex-col gap-3 pt-4 border-t border-zinc-800/50 mt-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleSwapTest(test.test_id)}
                        disabled={isSwapping === test.test_id}
                        className="px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded-lg text-sm font-bold transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                      >
                        {isSwapping === test.test_id ? (
                          <>
                            <Loader2 size={16} className="animate-spin" aria-hidden="true" /> Swapping...
                          </>
                        ) : (
                          <>
                            <Settings2 size={16} aria-hidden="true" /> Thumbnail 후보 이미지 즉시 교체
                          </>
                        )}
                      </button>
                      <button onClick={() => handleStopTest(test.test_id)} className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg text-sm font-bold transition-colors cursor-pointer flex items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400">
                        <CheckCircle2 size={16} aria-hidden="true" /> Lock Winning Thumbnail
                      </button>
                      <button onClick={() => handleDeleteTest(test.test_id)} className="ml-auto px-4 py-2 bg-zinc-700/50 hover:bg-red-900/40 text-zinc-200 hover:text-red-400 border border-zinc-500/50 hover:border-red-500/50 rounded-lg text-sm font-black transition-all cursor-pointer flex items-center gap-2 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400" title="테스트를 즉시 Cancel하고 유튜브 Thumbnail을 원본으로 복구합니다">
                        <Trash2 size={16} aria-hidden="true" /> 테스트 완전 Cancel 및 삭제
                      </button>
                    </div>
                    <div className="bg-zinc-800/30 rounded-lg p-3 text-xs text-zinc-400 leading-relaxed border border-zinc-800/50">
                      <strong className="text-zinc-300">💡 Thumbnail 즉시 교체란?</strong> 정해진 대기 시간을 무시하고 다음 Thumbnail 후보로 즉시 강제 교체해 보는 기능입니다.<br/>
                      (Note: Due to YouTube cache, it may take 1-2 minutes to reflect on YouTube after clicking the button.)
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
                    views={`${v.total_views_gained || 0}  views`}
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
  return (
    <div className={`relative glass-panel rounded-2xl p-5 flex flex-col transition-all duration-300 border ${isWinner ? "winner-glow transform -translate-y-1 border-cyan-500/50" : "border-zinc-800"}`}>
      {isWinner && (
        <div className="absolute -top-3 -right-2 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-bold px-3 py-1 rounded-full shadow-lg shadow-cyan-500/20 flex items-center gap-1 border border-cyan-400/50 z-20">
          <CheckCircle2 size={16} aria-hidden="true" /> 1위 승리
        </div>
      )}
      
      <div className="flex justify-between items-center mb-4 relative">
        <span className={`text-sm font-medium ${isWinner ? "text-cyan-400" : "text-zinc-300"}`}>{title}</span>
        
        </div>

      <div className="w-full aspect-video bg-zinc-800 rounded-lg mb-4 border border-zinc-700/50 flex items-center justify-center relative overflow-hidden group">
         {thumbnailUrl && thumbnailUrl.startsWith("http") ? (
           <img src={thumbnailUrl} alt={`${title} Thumbnail`} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
         ) : (
           <>
             <div className="absolute inset-0 bg-gradient-to-tr from-zinc-800 to-zinc-700 group-hover:scale-105 transition-transform duration-500" />
             <span className="relative z-10 text-zinc-400 font-medium">Thumbnail 이미지</span>
           </>
         )}
      </div>

      <div className="flex items-start justify-between gap-2 mb-6">
        <h3 className="text-sm font-semibold leading-tight line-clamp-2 text-zinc-100">{videoTitle}</h3>
      </div>

      <div className="mt-auto">
        <div className="flex justify-between items-end mb-2">
          <span className="text-sm text-zinc-400 uppercase font-medium tracking-wide">누적 상승 조회수</span>
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
              <span className="text-sm text-zinc-400 uppercase font-medium">Started At</span>
              <span className="text-lg font-bold text-zinc-100">{data[0]?.day || "-"}</span>
           </div>
           <div className="flex flex-col gap-1 text-right">
              <span className="text-sm text-zinc-400 uppercase font-medium">총 획득 조 views수</span>
              <span className="text-lg font-bold text-zinc-100">{views}</span>
           </div>
        </div>
      </div>
    </div>
  );
}
