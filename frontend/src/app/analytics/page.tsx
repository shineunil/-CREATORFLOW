"use client";

import React, { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, CartesianGrid, Tooltip as RechartsTooltip, LineChart, Line } from "recharts";
import { apiFetch } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<{ total_tests: number, active_tests: number, total_views_gained: number, trend: any[] }>({
    total_tests: 0,
    active_tests: 0,
    total_views_gained: 0,
    trend: []
  });

  useEffect(() => {
    apiFetch("/api/analytics")
      .then(res => res.json())
      .then(d => setData(d))
      .catch(console.error);
  }, []);

  return (
    <div className="w-full p-8 animate-fade-in-up">
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
      
      {/* 
        This is a placeholder for the trend chart.
        If trend data exists, render LineChart.
      */}
      <div className="glass-panel p-8 rounded-2xl border border-zinc-800/50">
         <h2 className="text-xl font-bold mb-6">Cumulative Extra Views Trend</h2>
         <div className="h-64 flex items-center justify-center border-t border-zinc-800/50 pt-8">
           <p className="text-zinc-500">Chart will appear when enough test data is accumulated.</p>
         </div>
      </div>
    </div>
  );
}
