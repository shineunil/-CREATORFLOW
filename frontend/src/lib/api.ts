import { API_BASE_URL } from "./config";
import { stripLocalePrefix } from "@/i18n/config";

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  // 백엔드 오류 메시지를 지금 보고 있는 화면 언어로 받기 위함 (<html lang>은 서버가 언어에 맞춰 설정)
  if (typeof document !== "undefined" && !headers.has("Accept-Language")) {
    headers.set("Accept-Language", document.documentElement.lang || "en");
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: "include", // L-3: HttpOnly 쿠키를 자동 전송 (Authorization 헤더 불필요)
  });

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("isLoggedIn");
      localStorage.removeItem("connectedChannel");
      const { path } = stripLocalePrefix(window.location.pathname);
      if (path !== "/" && path !== "/login") {
        window.location.href = "/login";
      }
    }
    throw new Error("Unauthorized");
  }

  // 로그인은 했지만 아직 YouTube 채널을 연결하지 않은 계정 - 채널이 필요한 화면 대신 연결 화면으로 보낸다
  if (response.status === 409 && typeof window !== "undefined") {
    const body = await response.clone().json().catch(() => null);
    if (body?.detail === "no_channel") {
      window.location.href = "/connect";
      throw new Error("No channel");
    }
  }

  return response;
}
