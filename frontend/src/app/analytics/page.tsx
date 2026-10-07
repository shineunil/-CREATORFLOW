"use client";

import React, { useState, useEffect } from "react";
import { BarChart, Bar, Cell, LabelList, XAxis, YAxis, ResponsiveContainer, CartesianGrid, ReferenceLine, Tooltip as RechartsTooltip } from "recharts";
import { Trophy, TrendingUp } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";
import ChannelSelect from "@/components/layout/ChannelSelect";
import { useI18n } from "@/i18n/I18nProvider";
import { formatNumber } from "@/i18n/format";
import TestInsights from "@/components/analytics/TestInsights";

type BestVariation = {
  name: string;
  title_text: string | null;
  thumbnail_image_url: string | null;
  total_views_gained: number;
  vph?: number;
  youtube_video_id: string;
};

type Lift = {
  test_id: number;
  title: string;
  winner_name: string;
  original_won: boolean;
  original_vph: number;
  winner_vph: number;
  lift_pct: number | null;
  na_reason?: string | null;
  end_time: string | null;
};

type Leader = {
  test_id: number;
  title: string;
  leader_name: string;
  leader_is_original: boolean;
  lift_pct: number | null;
  na_reason?: string | null;
};

/** 그래프 가로축용 짧은 제목 */
function shortTitle(title: string) {
  return title.length > 14 ? `${title.slice(0, 13)}…` : title;
}

function signed(pct: number) {
  return `${pct > 0 ? "+" : ""}${pct}%`;
}

export default function AnalyticsPage() {
  const { t, locale } = useI18n();
  const A = t.analytics;
  const [data, setData] = useState<{
    total_tests: number;
    active_tests: number;
    completed_tests?: number;
    stopped_tests?: number;
    best_variation: BestVariation | null;
    completed_lifts: Lift[];
    average_lift_pct: number | null;
    running_leaders: Leader[];
  }>({
    total_tests: 0,
    active_tests: 0,
    best_variation: null,
    completed_lifts: [],
    average_lift_pct: null,
    running_leaders: [],
  });
  // 원본을 측정하지 못했거나 원본 조회수 증가가 0이면 상승률을 계산할 수 없다 - 숨기지 않고 "비교 불가"로 보여 준다
  const lifts = data.completed_lifts || [];
  const chartRows = lifts.map((x) => ({ ...x, label: shortTitle(x.title), bar: x.lift_pct ?? 0 }));
  const liftText = (x: Lift | undefined) =>
    !x ? "" : x.original_won ? A.originalKept : x.lift_pct == null ? A.liftNa : signed(x.lift_pct);

  const loadAnalytics = () => {
    apiFetch("/api/analytics")
      .then(res => {
        if (!res.ok) throw new Error(`Failed to load analytics (${res.status})`);
        return res.json();
      })
      .then(d => setData(d))
      .catch(console.error);
  };

  useEffect(() => {
    loadAnalytics();

    // 좌측 상단 select box(또는 우측 상단 헤더)에서 다른 채널로 전환하면, 그 채널 기준
    // 통계로 새로고침 없이 다시 불러온다.
    window.addEventListener(CHANNEL_SWITCHED_EVENT, loadAnalytics);
    return () => window.removeEventListener(CHANNEL_SWITCHED_EVENT, loadAnalytics);
  }, []);

  return (
    <div className="w-full p-8 animate-fade-in-up">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-2">{A.title}</h1>
          <p className="text-zinc-400">{A.sub}</p>
        </div>
        <ChannelSelect />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
          <p className="text-zinc-400 text-sm mb-1">{A.totalTests}</p>
          <div className="text-4xl font-bold">{data.total_tests}</div>
          {/* 숫자가 무엇으로 이루어졌는지 (삭제한 테스트는 세지 않는다) */}
          <p className="text-xs text-zinc-400 mt-2 tabular-nums">
            {A.testBreakdown(data.completed_tests ?? 0, data.active_tests, data.stopped_tests ?? 0)}
          </p>
        </div>
        <div className="glass-panel p-6 rounded-2xl border border-emerald-500/20 bg-emerald-950/10">
          <p className="text-emerald-400/80 text-sm mb-1">{A.activeTests}</p>
          <div className="text-4xl font-bold text-emerald-400">{data.active_tests}</div>
        </div>
        {/* 실적: 원래 썸네일보다 이긴 썸네일이 시간당 조회수로 얼마나 나았는지 (끝난 테스트 평균) */}
        <div className="glass-panel p-6 rounded-2xl border border-cyan-500/20 bg-cyan-950/10" title={A.avgLiftHint}>
          <p className="text-cyan-400/80 text-sm mb-1">{A.avgLift}</p>
          {data.average_lift_pct != null ? (
            <div className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500 tabular-nums">
              {signed(data.average_lift_pct)}
            </div>
          ) : (
            <div className="text-base font-semibold text-zinc-400 mt-3">{A.avgLiftEmpty}</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-panel p-8 rounded-2xl border border-zinc-800/50 flex flex-col gap-6">
          <div>
            <h2 className="text-xl font-bold mb-1 flex items-center gap-2">
              <TrendingUp size={18} className="text-cyan-400" aria-hidden="true" /> {A.liftTitle}
            </h2>
            <p className="text-sm text-zinc-400 break-keep">{A.liftSub}</p>
          </div>

          {lifts.length === 0 ? (
            <div className="h-48 flex items-center justify-center border-t border-zinc-800/50">
              <p className="text-zinc-400 text-sm text-center break-keep">{A.liftEmpty}</p>
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartRows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="label" stroke="#71717a" fontSize={11} tickLine={false} axisLine={false} interval={0} />
                  <YAxis stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}%`} />
                  <ReferenceLine y={0} stroke="#52525b" />
                  <RechartsTooltip
                    cursor={{ fill: "rgba(255,255,255,0.04)" }}
                    contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
                    labelStyle={{ color: "#e4e4e7" }}
                    formatter={(_value, _name, item) => {
                      const lift = item?.payload as Lift | undefined;
                      const reason = lift?.lift_pct == null && lift?.na_reason ? ` - ${A.liftNaReasons[lift.na_reason] ?? ""}` : "";
                      return [`${liftText(lift)} (${lift?.winner_name ?? ""})${reason}`, A.liftLabel];
                    }}
                    wrapperStyle={{ maxWidth: 320, whiteSpace: "normal" }}
                    labelFormatter={(_label, payload) => (payload?.[0]?.payload as Lift | undefined)?.title ?? ""}
                  />
                  <Bar dataKey="bar" radius={[4, 4, 0, 0]} maxBarSize={56} minPointSize={4}>
                    {chartRows.map((x) => (
                      <Cell key={x.test_id} fill={(x.lift_pct ?? 0) > 0 ? "#06b6d4" : "#52525b"} />
                    ))}
                    {/* 막대 위 글자: 원본 유지·비교 불가는 막대 높이가 0이라 글자로 결과를 보여 준다 */}
                    <LabelList dataKey="test_id" position="top" fill="#e4e4e7" fontSize={12}
                      formatter={(id) => liftText(lifts.find((x) => x.test_id === Number(id)))} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 상승률을 계산할 수 없었던 끝난 테스트와 그 이유 */}
          {lifts.some((x) => x.lift_pct == null) && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4">
              <h3 className="text-sm font-bold text-amber-200 mb-2">{A.liftNaTitle}</h3>
              <ul className="flex flex-col gap-2">
                {lifts.filter((x) => x.lift_pct == null).map((x) => (
                  <li key={x.test_id} className="text-sm">
                    <span className="font-semibold text-zinc-200 break-keep">{x.title}</span>
                    <p className="text-zinc-400 break-keep mt-0.5">{(x.na_reason && A.liftNaReasons[x.na_reason]) || A.liftNa}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 진행 중인 테스트는 끝나기 전에도 지금 누가 원본보다 앞서는지 보여 준다 */}
          {data.running_leaders?.length > 0 && (
            <div className="border-t border-zinc-800/50 pt-5">
              <h3 className="text-sm font-bold text-zinc-200 mb-3">{A.runningTitle}</h3>
              <ul className="flex flex-col gap-2">
                {data.running_leaders.map((x) => (
                  <li key={x.test_id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
                    <span className="text-zinc-300 truncate min-w-0 max-w-full">{x.title}</span>
                    <span className={`font-bold tabular-nums ${x.lift_pct != null && x.lift_pct > 0 && !x.leader_is_original ? "text-cyan-400" : "text-zinc-400"}`}>
                      {x.leader_is_original
                        ? A.runningOriginalLead
                        : x.lift_pct == null
                          ? (x.na_reason && A.runningNaReasons[x.na_reason]) || A.runningPending
                          : A.runningLead(x.leader_name, x.lift_pct)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="glass-panel p-8 rounded-2xl border border-zinc-800/50 flex flex-col">
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <Trophy size={18} className="text-amber-400" aria-hidden="true" /> {A.bestTitle}
          </h2>
          {data.best_variation ? (
            <div className="flex flex-col gap-4">
              <div className="w-full aspect-video bg-zinc-800 rounded-lg overflow-hidden border border-zinc-700/50">
                {data.best_variation.thumbnail_image_url ? (
                  <img src={data.best_variation.thumbnail_image_url} alt={data.best_variation.name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-zinc-400 text-xs">{t.common.noImage}</div>
                )}
              </div>
              <div>
                <div className="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-1">{data.best_variation.name}</div>
                <h3 className="text-sm font-semibold text-zinc-100 line-clamp-2">{data.best_variation.title_text || A.noTitle}</h3>
              </div>
              <div className="mt-auto pt-4 border-t border-zinc-800/50 flex flex-col gap-2">
                {/* 테스트 승자와 같은 기준(시간당 조회수)으로 고른 썸네일 */}
                {data.best_variation.vph != null && (
                  <div className="flex justify-between items-end">
                    <span className="text-xs text-zinc-400 uppercase font-medium">{A.bestVph}</span>
                    <span className="text-xl font-bold text-cyan-400 tabular-nums">{formatNumber(data.best_variation.vph, locale)} VPH</span>
                  </div>
                )}
                <div className="flex justify-between items-end">
                  <span className="text-xs text-zinc-400 uppercase font-medium">{A.totalViewsGained}</span>
                  <span className="text-sm font-bold text-zinc-200 tabular-nums">+{formatNumber(data.best_variation.total_views_gained, locale)}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-center">
              <p className="text-zinc-400 text-sm">{A.noData}</p>
            </div>
          )}
        </div>
      </div>

      <TestInsights />
    </div>
  );
}
