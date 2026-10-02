"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Loader2, SquarePlay } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { SERVICE_UNAVAILABLE_ERROR, startChannelConnect } from "@/lib/auth";
import { useI18n } from "@/i18n/I18nProvider";
import LanguageSwitcher from "@/components/LanguageSwitcher";

/** 로그인은 했지만 아직 YouTube 채널이 없는 계정이 첫 채널을 연결하는 화면. */
function ConnectContent() {
  const { t, lp, locale } = useI18n();
  const C = t.connect;
  const router = useRouter();
  const searchParams = useSearchParams();
  const errorCode = searchParams.get("error");
  const errorMessage =
    errorCode === "channel_owned_elsewhere"
      ? t.dashboard.channelOwnedMsg(searchParams.get("channel") || "")
      : errorCode ? C.errors[errorCode] : null;
  const [email, setEmail] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    apiFetch("/api/user/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        // 이미 채널이 있는 계정이면 이 화면에 머물 이유가 없다
        if (data.has_channel) router.replace("/dashboard");
        else setEmail(data.email);
      })
      .catch(() => {});
  }, [router]);

  const handleConnect = async () => {
    if (isChecking) return;
    setIsChecking(true);
    if (!(await startChannelConnect(locale))) {
      router.push(`${lp("/login")}?error=${SERVICE_UNAVAILABLE_ERROR}`);
    }
  };

  const handleOtherAccount = () => {
    apiFetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    localStorage.removeItem("isLoggedIn");
    localStorage.removeItem("connectedChannel");
    router.replace(lp("/login"));
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-900/20 rounded-full blur-[150px] pointer-events-none" aria-hidden="true" />
      <LanguageSwitcher className="absolute top-8 right-8 inline-flex" />

      <div className="relative z-10 w-full max-w-md">
        <div className="flex flex-col items-center mb-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center text-white shadow-lg shadow-red-500/20 border border-red-400/30 mb-6" aria-hidden="true">
            <SquarePlay size={32} />
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight mb-2 text-balance">{C.title}</h1>
          <p className="text-zinc-400 text-sm break-keep">{C.sub}</p>
        </div>

        {errorMessage && (
          <div role="alert" className="mb-6 flex items-start gap-3 p-4 rounded-2xl bg-amber-950/30 border border-amber-500/30 text-amber-200 text-sm">
            <AlertTriangle size={18} className="text-amber-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span className="break-keep">{errorMessage}</span>
          </div>
        )}

        <div className="p-8 rounded-3xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur-xl shadow-2xl">
          <ol className="flex flex-col gap-3 mb-8 text-sm text-zinc-300">
            {C.steps.map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-zinc-800 text-cyan-400 text-xs font-bold flex items-center justify-center tabular-nums" aria-hidden="true">
                  {i + 1}
                </span>
                <span className="break-keep leading-relaxed">{step}</span>
              </li>
            ))}
          </ol>

          <button
            onClick={handleConnect}
            disabled={isChecking}
            aria-busy={isChecking}
            className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-white hover:bg-zinc-200 text-black rounded-xl font-bold transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-70 disabled:hover:scale-100 disabled:cursor-wait cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900"
          >
            {isChecking ? (
              <>
                <Loader2 size={20} className="animate-spin" aria-hidden="true" />
                {t.login.checking}
              </>
            ) : (
              <>
                <SquarePlay size={20} className="text-red-600" aria-hidden="true" />
                {C.button}
              </>
            )}
          </button>

          {email && <p className="mt-4 text-center text-xs text-zinc-400 break-all">{C.signedInAs(email)}</p>}
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={handleOtherAccount}
            className="text-sm text-zinc-400 hover:text-white underline underline-offset-2 transition-colors cursor-pointer rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            {C.otherAccount}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ConnectPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#09090b]" />}>
      <ConnectContent />
    </Suspense>
  );
}
