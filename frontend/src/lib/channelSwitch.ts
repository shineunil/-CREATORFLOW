import { apiFetch } from "./api";

// 채널 전환 성공 시 이 이벤트가 window에 발생한다. 채널에 따라 데이터를 보여주는 페이지/컴포넌트는
// 각자 이 이벤트를 구독해서 자기 데이터를 다시 불러오면 된다 (예전엔 window.location.reload()로
// 전체를 새로고침했는데, 그러면 화면이 깜빡이고 스크롤 위치 등도 다 날아가서 이벤트 기반으로 바꿨다).
export const CHANNEL_SWITCHED_EVENT = "channel-switched";

export async function switchChannel(channelId: number): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/channels/${channelId}/switch`, { method: "POST" });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem("jwt_token", data.token);
    window.dispatchEvent(new Event(CHANNEL_SWITCHED_EVENT));
    return true;
  } catch {
    return false;
  }
}
