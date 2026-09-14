"use client";

import React, { useEffect, useState } from "react";
import { ShieldAlert, Users, PlaySquare, FlaskConical, Gauge, AlertTriangle } from "lucide-react";
import { apiFetch } from "@/lib/api";

type Stats = {
  users: { total: number; pro: number; basic: number };
  channels: { total: number; needs_reconnect: number };
  tests: { active: number; completed: number; total: number };
  quota_today: { used: number; limit: number };
};

type AdminUser = {
  id: number;
  email: string;
  plan: string;
  created_at: string | null;
  channel_count: number;
  has_paddle_customer: boolean;
};

type AdminTest = {
  test_id: number;
  youtube_video_id: string;
  channel_title: string;
  user_email: string | null;
  needs_reconnect: boolean;
  swap_count: number;
  swap_failed: boolean;
  start_time: string | null;
};

export default function AdminPage() {
  const [status, setStatus] = useState<"loading" | "forbidden" | "error" | "ready">("loading");
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [tests, setTests] = useState<AdminTest[]>([]);

  useEffect(() => {
    Promise.all([
      apiFetch("/api/admin/stats"),
      apiFetch("/api/admin/users"),
      apiFetch("/api/admin/tests"),
    ])
      .then(async ([statsRes, usersRes, testsRes]) => {
        if (statsRes.status === 403 || usersRes.status === 403 || testsRes.status === 403) {
          setStatus("forbidden");
          return;
        }
        if (!statsRes.ok || !usersRes.ok || !testsRes.ok) {
          setStatus("error");
          return;
        }
        const [statsData, usersData, testsData] = await Promise.all([
          statsRes.json(),
          usersRes.json(),
          testsRes.json(),
        ]);
        setStats(statsData);
        setUsers(usersData.users || []);
        setTests(testsData.tests || []);
        setStatus("ready");
      })
      .catch((err) => {
        console.error(err);
        setStatus("error");
      });
  }, []);

  if (status === "loading") {
    return (
      <div className="w-full p-8 flex items-center justify-center text-zinc-400" role="status">
        Loading...
      </div>
    );
  }

  if (status === "forbidden") {
    return (
      <div className="w-full p-8 flex flex-col items-center justify-center text-center py-32">
        <ShieldAlert size={40} className="text-red-400 mb-4" aria-hidden="true" />
        <h1 className="text-xl font-bold text-white mb-2">Access Denied</h1>
        <p className="text-zinc-400 text-sm">This page is only accessible to admin accounts.</p>
      </div>
    );
  }

  if (status === "error" || !stats) {
    return (
      <div className="w-full p-8 flex flex-col items-center justify-center text-center py-32">
        <AlertTriangle size={40} className="text-amber-400 mb-4" aria-hidden="true" />
        <h1 className="text-xl font-bold text-white mb-2">Failed to Load Data</h1>
        <p className="text-zinc-400 text-sm">Please refresh in a moment.</p>
      </div>
    );
  }

  const quotaPct = stats.quota_today.limit > 0 ? Math.round((stats.quota_today.used / stats.quota_today.limit) * 100) : 0;

  return (
    <div className="w-full p-8 animate-fade-in-up">
      <div className="mb-8">
        <h1 className="text-3xl font-black text-white flex items-center gap-3">
          <ShieldAlert className="text-cyan-400" aria-hidden="true" /> Admin Dashboard
        </h1>
        <p className="text-zinc-400 mt-2">Overview of users, channels, tests, and API quota.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
        <StatCard icon={<Users size={18} aria-hidden="true" />} label="Total Users" value={`${stats.users.total}`} sub={`PRO ${stats.users.pro} / BASIC ${stats.users.basic}`} />
        <StatCard icon={<PlaySquare size={18} aria-hidden="true" />} label="Connected Channels" value={`${stats.channels.total}`} sub={stats.channels.needs_reconnect > 0 ? `${stats.channels.needs_reconnect} need reconnect` : "All normal"} warn={stats.channels.needs_reconnect > 0} />
        <StatCard icon={<FlaskConical size={18} aria-hidden="true" />} label="Active Tests" value={`${stats.tests.active}`} sub={`${stats.tests.total} total (${stats.tests.completed} completed)`} />
        <StatCard icon={<Gauge size={18} aria-hidden="true" />} label="Today's API Quota" value={`${quotaPct}%`} sub={`${stats.quota_today.used.toLocaleString()} / ${stats.quota_today.limit.toLocaleString()}`} warn={quotaPct >= 80} />
      </div>

      {/* Running tests */}
      <section className="glass-panel rounded-2xl border border-zinc-800/50 p-6 mb-8">
        <h2 className="text-lg font-bold mb-4">Active Tests ({tests.length})</h2>
        {tests.length === 0 ? (
          <p className="text-sm text-zinc-400">No active tests.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-zinc-400 border-b border-zinc-800/50">
                <tr>
                  <th className="py-2 pr-4 font-medium">User</th>
                  <th className="py-2 pr-4 font-medium">Channel</th>
                  <th className="py-2 pr-4 font-medium">Video ID</th>
                  <th className="py-2 pr-4 font-medium">Swaps</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {tests.map((t) => (
                  <tr key={t.test_id} className="border-b border-zinc-800/30 text-zinc-200">
                    <td className="py-2 pr-4">{t.user_email || "-"}</td>
                    <td className="py-2 pr-4">{t.channel_title || "-"}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{t.youtube_video_id}</td>
                    <td className="py-2 pr-4">{t.swap_count}</td>
                    <td className="py-2 pr-4">
                      {t.needs_reconnect ? (
                        <span className="text-amber-400 text-xs font-bold">Reconnect needed</span>
                      ) : t.swap_failed ? (
                        <span className="text-red-400 text-xs font-bold">Swap failed</span>
                      ) : (
                        <span className="text-emerald-400 text-xs font-bold">Normal</span>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-zinc-400 text-xs">{t.start_time ? new Date(t.start_time).toLocaleString() : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Users */}
      <section className="glass-panel rounded-2xl border border-zinc-800/50 p-6">
        <h2 className="text-lg font-bold mb-4">User List ({users.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-zinc-400 border-b border-zinc-800/50">
              <tr>
                <th className="py-2 pr-4 font-medium">Email</th>
                <th className="py-2 pr-4 font-medium">Plan</th>
                <th className="py-2 pr-4 font-medium">Channels</th>
                <th className="py-2 pr-4 font-medium">Payment History</th>
                <th className="py-2 pr-4 font-medium">Joined</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-zinc-800/30 text-zinc-200">
                  <td className="py-2 pr-4">{u.email}</td>
                  <td className="py-2 pr-4">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${u.plan === "PRO" ? "bg-cyan-500/10 text-cyan-400" : "bg-zinc-800 text-zinc-400"}`}>
                      {u.plan}
                    </span>
                  </td>
                  <td className="py-2 pr-4">{u.channel_count}</td>
                  <td className="py-2 pr-4">{u.has_paddle_customer ? "Yes" : "-"}</td>
                  <td className="py-2 pr-4 text-zinc-400 text-xs">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function StatCard({ icon, label, value, sub, warn }: { icon: React.ReactNode; label: string; value: string; sub: string; warn?: boolean }) {
  return (
    <div className={`glass-panel p-5 rounded-2xl border ${warn ? "border-amber-500/30 bg-amber-950/10" : "border-zinc-800/50"}`}>
      <div className="flex items-center gap-2 text-zinc-400 text-xs font-bold uppercase tracking-wider mb-2">
        {icon} {label}
      </div>
      <div className={`text-3xl font-black ${warn ? "text-amber-400" : "text-white"}`}>{value}</div>
      <div className="text-xs text-zinc-400 mt-1">{sub}</div>
    </div>
  );
}
