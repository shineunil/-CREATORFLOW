"use client";

import React, { useEffect, useState } from "react";
import { X, Megaphone } from "lucide-react";
import { apiFetch } from "@/lib/api";

type Announcement = {
  id: number;
  title: string;
  message: string;
  button_text: string | null;
  button_url: string | null;
};

function todayStr() {
  return new Date().toISOString().slice(0, 10); // "YYYY-MM-DD"
}

export default function AnnouncementPopup() {
  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const [visible, setVisible] = useState(false);
  const [hideToday, setHideToday] = useState(false);

  useEffect(() => {
    apiFetch("/api/announcement")
      .then(res => res.json())
      .then(data => {
        if (!data.announcement) return;
        const ann = data.announcement;
        try {
          const stored = localStorage.getItem(`ann_hide_${ann.id}`);
          if (stored === todayStr()) return; // 오늘 이미 닫은 경우
        } catch {}
        setAnnouncement(ann);
        setVisible(true);
      })
      .catch(() => {});
  }, []);

  const dismiss = () => {
    if (hideToday && announcement) {
      try {
        localStorage.setItem(`ann_hide_${announcement.id}`, todayStr());
      } catch {}
    }
    setVisible(false);
  };

  if (!visible || !announcement) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ann-popup-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
    >
      <div className="bg-zinc-950 border border-cyan-500/40 rounded-3xl p-6 md:p-8 max-w-md w-full shadow-[0_0_50px_rgba(6,182,212,0.2)] relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-cyan-500 via-blue-500 to-violet-500" aria-hidden="true" />

        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center gap-2">
            <Megaphone size={20} className="text-cyan-400" aria-hidden="true" />
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">Notice</span>
          </div>
          <button
            onClick={dismiss}
            aria-label="Close notice"
            className="text-zinc-400 hover:text-white p-1 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <h2 id="ann-popup-title" className="text-xl font-extrabold text-white mb-3">
          {announcement.title}
        </h2>
        <p className="text-zinc-300 text-sm leading-relaxed whitespace-pre-wrap mb-6">
          {announcement.message}
        </p>

        <label className="flex items-center gap-2 mb-4 cursor-pointer select-none group">
          <input
            type="checkbox"
            checked={hideToday}
            onChange={e => setHideToday(e.target.checked)}
            className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 accent-cyan-500 cursor-pointer"
          />
          <span className="text-xs text-zinc-400 group-hover:text-zinc-300 transition-colors">
            Don&apos;t show again today
          </span>
        </label>

        <div className="flex gap-3">
          {announcement.button_text && announcement.button_url && (
            <a
              href={announcement.button_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={dismiss}
              className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-sm text-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            >
              {announcement.button_text}
            </a>
          )}
          <button
            onClick={dismiss}
            className="flex-1 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-bold text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
