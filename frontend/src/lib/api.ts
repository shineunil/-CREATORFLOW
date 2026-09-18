import { API_BASE_URL } from "./config";

// JWT를 URL에 직접 싣지 않음 (C-1):
// OAuth 콜백은 ?auth_code=xxx를 URL에 싣고, 이 함수가 교환 엔드포인트를 호출해 실제 JWT를 받는다.
// 교환은 최초 1회만 발생하고 이후에는 localStorage에서 읽는다.
let _exchangePromise: Promise<string | null> | null = null;
let _cachedToken: string | null = null;

async function resolveToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  const url = new URL(window.location.href);
  const authCode = url.searchParams.get("auth_code");

  if (authCode) {
    if (!_exchangePromise) {
      _exchangePromise = (async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/auth/exchange?code=${encodeURIComponent(authCode)}`
          );
          if (!res.ok) return null;
          const data = await res.json();
          if (data?.token) {
            localStorage.setItem("jwt_token", data.token);
            _cachedToken = data.token;
          }
          // connected_channel은 채널 연동 성공 배너용
          const channelFromUrl = url.searchParams.get("connected_channel");
          if (channelFromUrl) {
            localStorage.setItem("connectedChannel", channelFromUrl);
          }
          url.searchParams.delete("auth_code");
          url.searchParams.delete("connected_channel");
          window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
          return data?.token ?? null;
        } catch {
          return null;
        }
      })();
    }
    return _exchangePromise;
  }

  // connected_channel이 URL에만 있는 경우 (배너 표시용, 별도 정리)
  const channelFromUrl = url.searchParams.get("connected_channel");
  if (channelFromUrl) {
    localStorage.setItem("connectedChannel", channelFromUrl);
    url.searchParams.delete("connected_channel");
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }

  return _cachedToken ?? localStorage.getItem("jwt_token");
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = await resolveToken();

  const headers = {
    ...options.headers,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("jwt_token");
      localStorage.removeItem("connectedChannel");
      _cachedToken = null;
      _exchangePromise = null;
      if (window.location.pathname !== "/" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    throw new Error("Unauthorized");
  }

  return response;
}
