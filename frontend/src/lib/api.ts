import { API_BASE_URL } from "./config";

function captureAuthFromUrl(): string | null {
  if (typeof window === "undefined") return null;

  const url = new URL(window.location.href);
  const urlToken = url.searchParams.get("token");
  if (!urlToken) return localStorage.getItem("jwt_token");

  localStorage.setItem("jwt_token", urlToken);
  const channelFromUrl = url.searchParams.get("connected_channel");
  if (channelFromUrl) {
    localStorage.setItem("connectedChannel", channelFromUrl);
  }

  url.searchParams.delete("token");
  url.searchParams.delete("connected_channel");
  const next = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState({}, "", next);
  return urlToken;
}

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = captureAuthFromUrl();

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
