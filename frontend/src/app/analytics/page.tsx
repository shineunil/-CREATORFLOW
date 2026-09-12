"use client";

import React, { useState, useEffect } from "react";
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip as RechartsTooltip } from "recharts";
import { Trophy } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";
import ChannelSelect from "@/components/layout/ChannelSelect";

type BestVariation = {
  name: string;
  title_text: string | null;
  thumbnail_image_url: string | null;
  total_views_gained: number;
  youtube_video_id: string;
};

export default function AnalyticsPage() {
  const [data, setData] = useState<{ total_tests: number, active_tests: number, total_views_gained: number, trend: any[], best_variation: BestVariation | null }>({
    total_tests: 0,
    active_tests: 0,
    total_views_gained: 0,
    trend: [],
    best_variation: null,
  });

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
      <div className="mb-4">
        <ChannelSelect />
      </div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Channel Analytics Overview</h1>
        <p className="text-zinc-400">Statistics of data optimized by CREATORFLOW.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="glass-panel p-6 rounded-2xl border border-zinc-800/50">
          <p className="text-zinc-400 text-sm mb-1">Total Optimizations</p>
          <div className="text-4xl font-bold">{data.total_tests}건</div>
        </div>
        <div className="glass-panel p-6 rounded-2xl border border-emerald-500/20 bg-emerald-950/10">
          <p className="text-emerald-400/80 text-sm mb-1">Active Optimizations</p>
          <div className="text-4xl font-bold text-emerald-400">{data.active_tests}건</div>
        </div>
        <div className="glass-panel p-6 rounded-2xl border border-cyan-500/20 bg-cyan-950/10">
          <p className="text-cyan-400/80 text-sm mb-1">Extra Views Gained from Optimization</p>
          <div className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
            +{data.total_views_gained.toLocaleString()}회
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-panel p-8 rounded-2xl border border-zinc-800/50">
          <h2 className="text-xl font-bold mb-6">Cumulative Extra Views Trend</h2>
          {data.trend.length === 0 ? (
            <div className="h-64 flex items-center justify-center border-t border-zinc-800/50 pt-8">
              <p className="text-zinc-400">Chart will appear when enough test data is accumulated.</p>
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.trend}>
                  <defs>
                    <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="day" stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#71717a" fontSize={12} tickLine={false} axisLine={false} />
                  <RechartsTooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} labelStyle={{ color: "#e4e4e7" }} />
                  <Area type="monotone" dataKey="views_gained" stroke="#06b6d4" strokeWidth={2} fill="url(#trendFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="glass-panel p-8 rounded-2xl border border-zinc-800/50 flex flex-col">
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <Trophy size={18} className="text-amber-400" aria-hidden="true" /> Best Performing Thumbnail
          </h2>
          {data.best_variation ? (
            <div className="flex flex-col gap-4">
              <div className="w-full aspect-video bg-zinc-800 rounded-lg overflow-hidden border border-zinc-700/50">
                {data.best_variation.thumbnail_image_url ? (
                  <img src={data.best_variation.thumbnail_image_url} alt={data.best_variation.name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-zinc-400 text-xs">No image</div>
                )}
              </div>
              <div>
                <div className="text-xs font-bold text-cyan-400 uppercase tracking-wider mb-1">{data.best_variation.name}</div>
                <h3 className="text-sm font-semibold text-zinc-100 line-clamp-2">{data.best_variation.title_text || "제목 없음"}</h3>
              </div>
              <div className="mt-auto pt-4 border-t border-zinc-800/50 flex justify-between items-end">
                <span className="text-xs text-zinc-400 uppercase font-medium">누적 상승 조회수</span>
                <span className="text-xl font-bold text-cyan-400">+{data.best_variation.total_views_gained.toLocaleString()}</span>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-center">
              <p className="text-zinc-400 text-sm">아직 측정된 데이터가 없습니다.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
