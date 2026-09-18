import { API_BASE_URL } from "./config";

// auth_code → JWT 교환은 ClientLayout.tsx에서 처리됨.
// apiFetch는 localStorage에 저장된 JWT만 읽는다.
function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("jwt_token");
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = getStoredToken();

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
      if (window.location.pathname !== "/" && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    throw new Error("Unauthorized");
  }

  return response;
}
