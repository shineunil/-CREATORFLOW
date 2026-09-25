"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";
import ChannelSelect from "@/components/layout/ChannelSelect";
import { useI18n } from "@/i18n/I18nProvider";
import { formatDate, formatNumber } from "@/i18n/format";

export default function HistoryPage() {
  const { t, locale } = useI18n();
  const [tests, setTests] = useState<any[]>([]);

  const loadHistory = () => {
    apiFetch("/api/history")
      .then(res => {
        if (!res.ok) throw new Error(`Failed to load history (${res.status})`);
        return res.json();
      })
      .then(data => {
        setTests(data.tests || []);
      })
      .catch(console.error);
  };

  useEffect(() => {
    loadHistory();
    window.addEventListener(CHANNEL_SWITCHED_EVENT, loadHistory);
    return () => window.removeEventListener(CHANNEL_SWITCHED_EVENT, loadHistory);
  }, []);

  return (
    <div className="w-full p-8 animate-fade-in-up">
      <div className="mb-4">
        <ChannelSelect />
      </div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">{t.history.title}</h1>
        <p className="text-zinc-400">{t.history.sub}</p>
      </div>

      <div className="space-y-6">
        {tests.length === 0 ? (
          <div className="text-center py-20 text-zinc-400 glass-panel rounded-2xl border border-zinc-800/50">
            {t.history.empty}
          </div>
        ) : (
          tests.map((test, i) => (
            <div key={i} className="glass-panel p-6 rounded-2xl border border-zinc-800/50 flex flex-col md:flex-row justify-between gap-6">
              <div>
                <p className="text-xs text-zinc-400 mb-2">{t.history.ended(formatDate(test.end_time, locale))}</p>
                <h3 className="text-lg font-bold">{test.video?.youtube_video_id}</h3>
              </div>
              <div className="flex gap-4">
                {test.variations?.map((v: any) => (
                  <div key={v.id} className="p-3 bg-zinc-900/50 rounded-lg text-sm border border-zinc-800">
                    <div className="font-bold">{v.title_text}</div>
                    <div className="text-zinc-400">{t.history.viewsGained(formatNumber(v.views_gained ?? 0, locale))}</div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
