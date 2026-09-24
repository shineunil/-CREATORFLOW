import { apiFetch } from "./api";

type PaddleGlobal = {
  Environment: { set: (env: string) => void };
  Initialize: (options: { token: string }) => void;
  Checkout: {
    open: (options: {
      transactionId: string;
      settings?: { displayMode?: "overlay"; successUrl?: string };
    }) => void;
  };
};

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

const PADDLE_JS_URL = "https://cdn.paddle.com/paddle/v2/paddle.js";

let paddleLoad: Promise<PaddleGlobal> | null = null;
let initializedToken: string | null = null;

function loadPaddle(): Promise<PaddleGlobal> {
  if (window.Paddle) return Promise.resolve(window.Paddle);
  if (!paddleLoad) {
    paddleLoad = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = PADDLE_JS_URL;
      script.async = true;
      script.onload = () =>
        window.Paddle ? resolve(window.Paddle) : reject(new Error("Paddle.js failed to load."));
      script.onerror = () => {
        paddleLoad = null;
        reject(new Error("Could not load the payment window. Check your connection and try again."));
      };
      document.head.appendChild(script);
    });
  }
  return paddleLoad;
}

export async function openPaddleCheckout(): Promise<void> {
  const res = await apiFetch("/api/checkout/create-session", { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error (${res.status})`);
  }
  const { transaction_id, client_token, environment } = await res.json();

  const Paddle = await loadPaddle();
  // Paddle.js는 페이지당 한 번만 초기화하며, Environment.set은 Initialize보다 먼저 호출해야 한다.
  if (initializedToken !== client_token) {
    if (environment === "sandbox") Paddle.Environment.set("sandbox");
    Paddle.Initialize({ token: client_token });
    initializedToken = client_token;
  }

  Paddle.Checkout.open({
    transactionId: transaction_id,
    settings: {
      displayMode: "overlay",
      successUrl: `${window.location.origin}/dashboard?upgraded=true`,
    },
  });
}
