import { API_BASE_URL } from "./config";

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    credentials: "include", // L-3: HttpOnly 쿠키를 자동 전송 (Authorization 헤더 불필요)
  });

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("isLoggedIn");
      localStorage.removeItem("connectedChannel");
      if (window.location.pathname !== "/" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    throw new Error("Unauthorized");
  }

  return response;
}
