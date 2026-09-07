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
        불러오는 중...
      </div>
    );
  }

  if (status === "forbidden") {
    return (
      <div className="w-full p-8 flex flex-col items-center justify-center text-center py-32">
        <ShieldAlert size={40} className="text-red-400 mb-4" aria-hidden="true" />
        <h1 className="text-xl font-bold text-white mb-2">접근 권한이 없습니다</h1>
        <p className="text-zinc-400 text-sm">이 페이지는 관리자 계정만 볼 수 있습니다.</p>
      </div>
    );
  }

  if (status === "error" || !stats) {
    return (
      <div className="w-full p-8 flex flex-col items-center justify-center text-center py-32">
        <AlertTriangle size={40} className="text-amber-400 mb-4" aria-hidden="true" />
        <h1 className="text-xl font-bold text-white mb-2">데이터를 불러오지 못했습니다</h1>
        <p className="text-zinc-400 text-sm">잠시 후 새로고침 해주세요.</p>
      </div>
    );
  }

  const quotaPct = stats.quota_today.limit > 0 ? Math.round((stats.quota_today.used / stats.quota_today.limit) * 100) : 0;

  return (
    <div className="w-full p-8 animate-fade-in-up">
      <div className="mb-8">
        <h1 className="text-3xl font-black text-white flex items-center gap-3">
          <ShieldAlert className="text-cyan-400" aria-hidden="true" /> 관리자 대시보드
        </h1>
        <p className="text-zinc-400 mt-2">가입자, 채널, 테스트, API 쿼터 현황을 한눈에 확인합니다.</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
        <StatCard icon={<Users size={18} aria-hidden="true" />} label="전체 가입자" value={`${stats.users.total}`} sub={`PRO ${stats.users.pro} / BASIC ${stats.users.basic}`} />
        <StatCard icon={<PlaySquare size={18} aria-hidden="true" />} label="연동 채널" value={`${stats.channels.total}`} sub={stats.channels.needs_reconnect > 0 ? `재연동 필요 ${stats.channels.needs_reconnect}개` : "전부 정상"} warn={stats.channels.needs_reconnect > 0} />
        <StatCard icon={<FlaskConical size={18} aria-hidden="true" />} label="진행 중 테스트" value={`${stats.tests.active}`} sub={`누적 ${stats.tests.total}개 (완료 ${stats.tests.completed})`} />
        <StatCard icon={<Gauge size={18} aria-hidden="true" />} label="오늘 API 쿼터" value={`${quotaPct}%`} sub={`${stats.quota_today.used.toLocaleString()} / ${stats.quota_today.limit.toLocaleString()}`} warn={quotaPct >= 80} />
      </div>

      {/* Running tests */}
      <section className="glass-panel rounded-2xl border border-zinc-800/50 p-6 mb-8">
        <h2 className="text-lg font-bold mb-4">진행 중인 테스트 ({tests.length})</h2>
        {tests.length === 0 ? (
          <p className="text-sm text-zinc-400">현재 진행 중인 테스트가 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-zinc-400 border-b border-zinc-800/50">
                <tr>
                  <th className="py-2 pr-4 font-medium">유저</th>
                  <th className="py-2 pr-4 font-medium">채널</th>
                  <th className="py-2 pr-4 font-medium">영상 ID</th>
                  <th className="py-2 pr-4 font-medium">스왑 횟수</th>
                  <th className="py-2 pr-4 font-medium">상태</th>
                  <th className="py-2 pr-4 font-medium">시작일</th>
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
                        <span className="text-amber-400 text-xs font-bold">재연동 필요</span>
                      ) : t.swap_failed ? (
                        <span className="text-red-400 text-xs font-bold">스왑 실패</span>
                      ) : (
                        <span className="text-emerald-400 text-xs font-bold">정상</span>
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
        <h2 className="text-lg font-bold mb-4">가입자 목록 ({users.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-zinc-400 border-b border-zinc-800/50">
              <tr>
                <th className="py-2 pr-4 font-medium">이메일</th>
                <th className="py-2 pr-4 font-medium">플랜</th>
                <th className="py-2 pr-4 font-medium">채널 수</th>
                <th className="py-2 pr-4 font-medium">결제 이력</th>
                <th className="py-2 pr-4 font-medium">가입일</th>
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
                  <td className="py-2 pr-4">{u.has_paddle_customer ? "있음" : "-"}</td>
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
