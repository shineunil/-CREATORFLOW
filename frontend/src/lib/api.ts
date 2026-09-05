import { API_BASE_URL } from "./config";

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  let token = typeof window !== "undefined" ? localStorage.getItem("jwt_token") : null;
  
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      token = urlToken;
      localStorage.setItem("jwt_token", urlToken);
      
      const channelFromUrl = params.get("connected_channel");
      if (channelFromUrl) {
        localStorage.setItem("connectedChannel", channelFromUrl);
      }
    }
  }

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
