"use client";

import React, { useEffect, useState, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { switchChannel, CHANNEL_SWITCHED_EVENT } from "@/lib/channelSwitch";
import { useI18n } from "@/i18n/I18nProvider";

type ChannelSummary = {
  id: number;
  channel_title: string;
  is_connected: boolean;
  is_active: boolean;
};

// 대시보드 / New Test 페이지 좌측 상단에서 지금 연동된 채널을 보여주고 바로 전환할 수 있는
// select box. TopHeader 우측 상단 드롭다운과 기능은 같고(둘 다 channelSwitch.ts를 공유),
// 이 페이지들에서 더 눈에 띄게 좌측에 두기 위한 용도다.
export default function ChannelSelect() {
  const { t } = useI18n();
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [isSwitching, setIsSwitching] = useState(false);
  const isSwitchingRef = useRef(false);

  const loadChannels = () => {
    apiFetch("/api/channels")
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setChannels(data.channels || []))
      .catch(() => {});
  };

  useEffect(() => {
    if (!localStorage.getItem("isLoggedIn")) return;
    loadChannels();

    const handleChannelSwitched = () => loadChannels();
    window.addEventListener(CHANNEL_SWITCHED_EVENT, handleChannelSwitched);
    return () => window.removeEventListener(CHANNEL_SWITCHED_EVENT, handleChannelSwitched);
  }, []);

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextId = parseInt(e.target.value, 10);
    const current = channels.find((c) => c.is_active);
    if (!current || nextId === current.id || isSwitchingRef.current) return;

    isSwitchingRef.current = true;
    setIsSwitching(true);
    await switchChannel(nextId);
    isSwitchingRef.current = false;
    setIsSwitching(false);
  };

  if (channels.length === 0) return null;

  const activeId = channels.find((c) => c.is_active)?.id ?? channels[0].id;

  return (
    <div className="inline-flex items-center gap-3">
      <label htmlFor="channel-select" className="text-base font-bold text-zinc-100">
        {t.channelSelect.label}
      </label>
      <select
        id="channel-select"
        value={activeId}
        onChange={handleChange}
        disabled={isSwitching}
        className="bg-zinc-800 border border-zinc-600 hover:border-zinc-400 rounded-xl px-4 py-2 text-base font-bold text-white focus:outline-none focus:border-cyan-500 disabled:opacity-60 disabled:cursor-wait cursor-pointer transition-colors"
      >
        {channels.map((c) => (
          <option key={c.id} value={c.id}>
            {c.channel_title || t.common.untitled}{!c.is_connected ? t.channelSelect.disconnectedSuffix : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
