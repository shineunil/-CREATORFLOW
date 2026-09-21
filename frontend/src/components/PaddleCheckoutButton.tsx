"use client";

import { useState } from "react";
import { CreditCard, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function PaddleCheckoutButton() {
  const [isLoading, setIsLoading] = useState(false);

  const handleCheckout = async () => {
    setIsLoading(true);
    try {
      const res = await apiFetch("/api/checkout/create-session", { method: "POST" });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error (${res.status})`);
      }
      const { checkout_url } = await res.json();
      window.location.href = checkout_url;
    } catch (err: any) {
      console.error("Paddle Checkout Error:", err);
      alert(err.message || "Failed to start checkout. Please try again.");
      setIsLoading(false);
    }
  };

  return (
    <button
      onClick={handleCheckout}
      disabled={isLoading}
      className="w-full py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:from-zinc-700 disabled:to-zinc-700 disabled:cursor-not-allowed text-white font-extrabold transition-all shadow-lg hover:shadow-cyan-500/25 flex items-center justify-center gap-2 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
    >
      {isLoading ? (
        <>
          <Loader2 size={18} className="animate-spin" aria-hidden="true" />
          <span>Redirecting to Paddle...</span>
        </>
      ) : (
        <>
          <CreditCard size={18} aria-hidden="true" />
          <span>Upgrade to PRO — $29/mo</span>
        </>
      )}
    </button>
  );
}
