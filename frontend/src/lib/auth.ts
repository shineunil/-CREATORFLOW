import { API_BASE_URL } from "@/lib/config";

/** 정식 오픈 시각 (한국 시간 10/3 0시). 이 전에는 "오픈 예정", 이후에는 "점검 중" 안내를 보여준다. */
export const LAUNCH_AT = new Date("2026-10-03T00:00:00+09:00");

export const SERVICE_UNAVAILABLE_ERROR = "unavailable";

const STATUS_TIMEOUT_MS = 8000;

/**
 * 백엔드가 "확실히" 꺼져 있을 때만 true.
 * 꺼진 서버(Render 503 화면 등)나 연결 실패는 바로 알 수 있지만, 응답이 느린 경우(서버가 깨어나는 중)는
 * 꺼졌다고 단정하지 않고 로그인을 그대로 진행한다 - 기다리면 정상 로그인되기 때문.
 */
async function isBackendDown(): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), STATUS_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE_URL}/api/status`, { cache: "no-store", signal: controller.signal });
    return !res.ok;
  } catch {
    return !controller.signal.aborted;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 개인 구글 계정으로 로그인을 시작한다. 백엔드가 꺼져 있으면 Render 오류 화면으로 보내지 않고 false를 돌려준다
 * - 호출한 쪽이 우리 안내(오픈 예정 / 점검 중)를 보여준다.
 */
export async function startGoogleLogin(locale: string): Promise<boolean> {
  if (await isBackendDown()) return false;
  window.location.href = `${API_BASE_URL}/api/auth/login?locale=${locale}`;
  return true;
}

/**
 * 로그인한 계정에 YouTube 채널을 연결한다 (첫 연결·채널 추가·다시 연동). 서버가 꺼져 있으면 false.
 * reconnectChannelId를 주면 "그 채널 다시 연동" 모드 - 구글에서 다른 채널을 고르면 서버가 연동하지 않는다.
 */
export async function startChannelConnect(locale: string, reconnectChannelId?: number): Promise<boolean> {
  if (await isBackendDown()) return false;
  const reconnect = reconnectChannelId ? `&reconnect=${reconnectChannelId}` : "";
  window.location.href = `${API_BASE_URL}/api/auth/connect?locale=${locale}${reconnect}`;
  return true;
}
