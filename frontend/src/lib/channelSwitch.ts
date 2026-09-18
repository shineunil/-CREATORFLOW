import { apiFetch } from "./api";

export const CHANNEL_SWITCHED_EVENT = "channel-switched";

export async function switchChannel(channelId: number): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/channels/${channelId}/switch`, { method: "POST" });
    if (!res.ok) return false;
    // L-3: 새 채널 토큰은 백엔드가 HttpOnly 쿠키로 설정 — localStorage에 저장 불필요
    window.dispatchEvent(new Event(CHANNEL_SWITCHED_EVENT));
    return true;
  } catch {
    return false;
  }
}
