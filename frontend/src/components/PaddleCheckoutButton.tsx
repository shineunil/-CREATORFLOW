"use client";

import { useState } from "react";
import { CreditCard, Loader2 } from "lucide-react";
import { openPaddleCheckout } from "@/lib/paddle";
import { useI18n } from "@/i18n/I18nProvider";

export default function PaddleCheckoutButton() {
  const { t, locale } = useI18n();
  const [isLoading, setIsLoading] = useState(false);

  const handleCheckout = async () => {
    setIsLoading(true);
    try {
      await openPaddleCheckout(locale);
    } catch (err: unknown) {
      console.error("Paddle Checkout Error:", err);
      if (!(err instanceof Error && err.message === "Unauthorized")) {
        alert(err instanceof Error ? err.message : t.checkout.failed);
      }
    } finally {
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
          <span>{t.checkout.opening}</span>
        </>
      ) : (
        <>
          <CreditCard size={18} aria-hidden="true" />
          <span>{t.checkout.upgrade}</span>
        </>
      )}
    </button>
  );
}
